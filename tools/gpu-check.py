#!/usr/bin/env python3
"""Probe NVIDIA GPU availability without nvidia-smi or a CUDA toolkit.

`yolo --nvidia` hands the container GPU access through CDI, which injects the
host's driver libraries and device nodes but not necessarily the `nvidia-smi`
binary.  This script checks the same things nvidia-smi would, plus an actual
compute round-trip, using only the Python standard library:

  * the kernel driver, via /proc/driver/nvidia
  * telemetry, via NVML (libnvidia-ml.so.1) -- what nvidia-smi is a CLI over
  * compute, via the CUDA driver API (libcuda.so.1): context, allocation,
    host<->device copies, a device-side memset, and a JIT-compiled kernel

Exit codes:
  0  GPU present and usable for compute
  1  GPU present but one of the checks failed
  2  no GPU or driver visible here
"""

import argparse
import ctypes
import glob
import json
import os
import sys

PROC_VERSION = "/proc/driver/nvidia/version"
PROC_GPUS = "/proc/driver/nvidia/gpus"

# CUdevice_attribute
ATTR_MULTIPROCESSOR_COUNT = 16
ATTR_COMPUTE_CAPABILITY_MAJOR = 75
ATTR_COMPUTE_CAPABILITY_MINOR = 76

# A vector add, as PTX so the driver JITs it -- no nvcc needed.  {target} is
# filled in from the device's own compute capability.
PTX_TEMPLATE = """//
.version {version}
.target {target}
.address_size 64

.visible .entry vecadd(
    .param .u64 vecadd_param_0,
    .param .u64 vecadd_param_1,
    .param .u32 vecadd_param_2
)
{{
    .reg .pred  %p<2>;
    .reg .f32   %f<4>;
    .reg .b32   %r<6>;
    .reg .b64   %rd<8>;

    ld.param.u64    %rd1, [vecadd_param_0];
    ld.param.u64    %rd2, [vecadd_param_1];
    ld.param.u32    %r2, [vecadd_param_2];
    mov.u32         %r3, %ctaid.x;
    mov.u32         %r4, %ntid.x;
    mov.u32         %r5, %tid.x;
    mad.lo.s32      %r1, %r3, %r4, %r5;
    setp.ge.s32     %p1, %r1, %r2;
    @%p1 bra        DONE;

    cvta.to.global.u64  %rd3, %rd1;
    mul.wide.s32        %rd4, %r1, 4;
    add.s64             %rd5, %rd3, %rd4;
    ld.global.f32       %f1, [%rd5];
    cvta.to.global.u64  %rd6, %rd2;
    add.s64             %rd7, %rd6, %rd4;
    ld.global.f32       %f2, [%rd7];
    add.f32             %f3, %f1, %f2;
    st.global.f32       [%rd7], %f3;

DONE:
    ret;
}}
"""


class CudaError(RuntimeError):
    pass


def load(name):
    """Load a shared library, or return None if it is not present."""
    try:
        return ctypes.CDLL(name)
    except OSError:
        return None


def bind(lib, name, restype, *argtypes):
    """Declare a library function's signature.

    ctypes would otherwise truncate 64-bit pointers to int, so every call the
    checker makes goes through here.
    """
    fn = getattr(lib, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


# ── kernel driver ─────────────────────────────────────────────────


def probe_driver():
    """Read what the kernel module exposes through /proc and /dev."""
    info = {"loaded": False, "version": None, "device_nodes": [], "gpus": []}

    info["device_nodes"] = sorted(
        os.path.basename(p) for p in glob.glob("/dev/nvidia*")
    )

    try:
        with open(PROC_VERSION) as fh:
            first = fh.readline().strip()
    except OSError:
        return info

    info["loaded"] = True
    # "NVRM version: NVIDIA UNIX x86_64 Kernel Module  590.48.01  Mon Dec ..."
    for token in first.split():
        if token[0].isdigit() and "." in token:
            info["version"] = token
            break

    for path in sorted(glob.glob(os.path.join(PROC_GPUS, "*", "information"))):
        gpu = {}
        try:
            with open(path) as fh:
                for line in fh:
                    key, _, value = line.partition(":")
                    gpu[key.strip().lower().replace(" ", "_")] = value.strip()
        except OSError:
            continue
        info["gpus"].append(
            {
                "bus_id": os.path.basename(os.path.dirname(path)),
                "model": gpu.get("model"),
                "uuid": gpu.get("gpu_uuid"),
                "excluded": gpu.get("gpu_excluded"),
            }
        )

    return info


# ── NVML (the nvidia-smi substitute) ──────────────────────────────


class Nvml:
    """Minimal NVML binding: the telemetry nvidia-smi prints."""

    def __init__(self, lib):
        self.lib = lib
        self.init = bind(lib, "nvmlInit_v2", ctypes.c_int)
        self.shutdown = bind(lib, "nvmlShutdown", ctypes.c_int)
        self.count = bind(
            lib, "nvmlDeviceGetCount_v2", ctypes.c_int, ctypes.POINTER(ctypes.c_uint)
        )
        self.handle = bind(
            lib,
            "nvmlDeviceGetHandleByIndex_v2",
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
        )

    class _Util(ctypes.Structure):
        _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

    class _Mem(ctypes.Structure):
        _fields_ = [
            ("total", ctypes.c_ulonglong),
            ("free", ctypes.c_ulonglong),
            ("used", ctypes.c_ulonglong),
        ]

    def telemetry(self):
        """Return per-index telemetry dicts, or {} if NVML will not start."""
        if self.init() != 0:
            return {}
        out = {}
        try:
            n = ctypes.c_uint()
            if self.count(ctypes.byref(n)) != 0:
                return {}
            for i in range(n.value):
                h = ctypes.c_void_p()
                if self.handle(i, ctypes.byref(h)) != 0:
                    continue
                entry = {}
                util = self._Util()
                if self.lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util)) == 0:
                    entry["utilization_pct"] = util.gpu
                    entry["memory_utilization_pct"] = util.memory
                mem = self._Mem()
                if self.lib.nvmlDeviceGetMemoryInfo(h, ctypes.byref(mem)) == 0:
                    entry["memory_used_mib"] = mem.used >> 20
                    entry["memory_total_mib"] = mem.total >> 20
                temp = ctypes.c_uint()
                if self.lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(temp)) == 0:
                    entry["temperature_c"] = temp.value
                power = ctypes.c_uint()
                if self.lib.nvmlDeviceGetPowerUsage(h, ctypes.byref(power)) == 0:
                    entry["power_w"] = round(power.value / 1000.0, 1)
                out[i] = entry
        finally:
            self.shutdown()
        return out


# ── CUDA driver API ───────────────────────────────────────────────


class Cuda:
    """Enough of the CUDA driver API to prove the device really computes."""

    def __init__(self, lib):
        self.lib = lib
        u32, vp, sz = ctypes.c_uint, ctypes.c_void_p, ctypes.c_size_t
        p_int, p_vp, p_sz = (
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
        )
        self.init = bind(lib, "cuInit", ctypes.c_int, u32)
        self.driver_version = bind(lib, "cuDriverGetVersion", ctypes.c_int, p_int)
        self.device_count = bind(lib, "cuDeviceGetCount", ctypes.c_int, p_int)
        self.device_get = bind(lib, "cuDeviceGet", ctypes.c_int, p_int, ctypes.c_int)
        self.device_name = bind(
            lib, "cuDeviceGetName", ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
            ctypes.c_int,
        )
        self.device_attr = bind(
            lib, "cuDeviceGetAttribute", ctypes.c_int, p_int, ctypes.c_int,
            ctypes.c_int,
        )
        self.total_mem = bind(
            lib, "cuDeviceTotalMem_v2", ctypes.c_int, p_sz, ctypes.c_int
        )
        self.ctx_create = bind(
            lib, "cuCtxCreate_v2", ctypes.c_int, p_vp, u32, ctypes.c_int
        )
        self.ctx_destroy = bind(lib, "cuCtxDestroy_v2", ctypes.c_int, vp)
        self.ctx_sync = bind(lib, "cuCtxSynchronize", ctypes.c_int)
        self.mem_alloc = bind(lib, "cuMemAlloc_v2", ctypes.c_int, p_vp, sz)
        self.mem_free = bind(lib, "cuMemFree_v2", ctypes.c_int, vp)
        self.mem_info = bind(lib, "cuMemGetInfo_v2", ctypes.c_int, p_sz, p_sz)
        self.memcpy_h2d = bind(lib, "cuMemcpyHtoD_v2", ctypes.c_int, vp, vp, sz)
        self.memcpy_d2h = bind(lib, "cuMemcpyDtoH_v2", ctypes.c_int, vp, vp, sz)
        self.memset_d32 = bind(lib, "cuMemsetD32_v2", ctypes.c_int, vp, u32, sz)
        self.module_load = bind(lib, "cuModuleLoadData", ctypes.c_int, p_vp, vp)
        self.module_unload = bind(lib, "cuModuleUnload", ctypes.c_int, vp)
        self.module_func = bind(
            lib, "cuModuleGetFunction", ctypes.c_int, p_vp, vp, ctypes.c_char_p
        )
        self.launch = bind(
            lib, "cuLaunchKernel", ctypes.c_int, vp, u32, u32, u32, u32, u32, u32,
            u32, vp, p_vp, p_vp,
        )
        self.error_string = bind(
            lib, "cuGetErrorString", ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
        )

    def check(self, code, what):
        if code != 0:
            msg = ctypes.c_char_p()
            self.error_string(code, ctypes.byref(msg))
            detail = msg.value.decode() if msg.value else "unknown error"
            raise CudaError(f"{what}: {detail} (CUresult {code})")


def ptx_isa_version(driver_version):
    """Pick a PTX ISA version the running driver's JIT will accept."""
    major = driver_version // 1000
    return {11: "7.0", 12: "8.0"}.get(major, "9.0" if major >= 13 else "7.0")


def check_kernel_launch(cuda, cc_major, cc_minor, isa):
    """JIT a vector-add kernel from PTX, run it, verify the result."""
    n = 1 << 20
    ptx = PTX_TEMPLATE.format(
        version=isa, target="sm_{}{}".format(cc_major, cc_minor)
    ).encode()

    module = ctypes.c_void_p()
    cuda.check(cuda.module_load(ctypes.byref(module), ptx), "cuModuleLoadData")
    try:
        func = ctypes.c_void_p()
        cuda.check(
            cuda.module_func(ctypes.byref(func), module, b"vecadd"),
            "cuModuleGetFunction",
        )

        nbytes = n * 4
        d_a, d_b = ctypes.c_void_p(), ctypes.c_void_p()
        cuda.check(cuda.mem_alloc(ctypes.byref(d_a), nbytes), "cuMemAlloc(a)")
        cuda.check(cuda.mem_alloc(ctypes.byref(d_b), nbytes), "cuMemAlloc(b)")
        try:
            # Only the first `checked` elements carry a known value; the rest
            # stay zero, so the kernel still runs over the whole vector.
            checked = 1024
            host_a, host_b = (ctypes.c_float * n)(), (ctypes.c_float * n)()
            for i in range(checked):
                host_a[i], host_b[i] = 1.5, 2.5
            cuda.check(cuda.memcpy_h2d(d_a, host_a, nbytes), "cuMemcpyHtoD(a)")
            cuda.check(cuda.memcpy_h2d(d_b, host_b, nbytes), "cuMemcpyHtoD(b)")

            count = ctypes.c_int(n)
            params = (ctypes.c_void_p * 3)(
                ctypes.cast(ctypes.byref(d_a), ctypes.c_void_p),
                ctypes.cast(ctypes.byref(d_b), ctypes.c_void_p),
                ctypes.cast(ctypes.byref(count), ctypes.c_void_p),
            )
            block = 256
            grid = (n + block - 1) // block
            cuda.check(
                cuda.launch(func, grid, 1, 1, block, 1, 1, 0, None, params, None),
                "cuLaunchKernel",
            )
            cuda.check(cuda.ctx_sync(), "cuCtxSynchronize")

            out = (ctypes.c_float * n)()
            cuda.check(cuda.memcpy_d2h(out, d_b, nbytes), "cuMemcpyDtoH")
            if not all(abs(out[i] - 4.0) < 1e-6 for i in range(checked)):
                raise CudaError("vector add produced wrong results")
            return "{} elements, JIT from PTX ISA {}".format(n, isa)
        finally:
            cuda.mem_free(d_a)
            cuda.mem_free(d_b)
    finally:
        cuda.module_unload(module)


def ok(detail=None):
    return {"ok": True, "detail": detail}


def failed(detail):
    return {"ok": False, "detail": str(detail)}


def probe_device(cuda, index, alloc_mib):
    """Run every compute check against one device; never raises."""
    dev = {"index": index, "checks": {}}

    handle = ctypes.c_int()
    cuda.check(cuda.device_get(ctypes.byref(handle), index), "cuDeviceGet")

    name = ctypes.create_string_buffer(256)
    cuda.device_name(name, 256, handle)
    dev["name"] = name.value.decode()

    major, minor, sms = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
    cuda.device_attr(ctypes.byref(major), ATTR_COMPUTE_CAPABILITY_MAJOR, handle)
    cuda.device_attr(ctypes.byref(minor), ATTR_COMPUTE_CAPABILITY_MINOR, handle)
    cuda.device_attr(ctypes.byref(sms), ATTR_MULTIPROCESSOR_COUNT, handle)
    dev["compute_capability"] = "{}.{}".format(major.value, minor.value)
    dev["multiprocessors"] = sms.value

    total = ctypes.c_size_t()
    cuda.total_mem(ctypes.byref(total), handle)
    dev["memory_total_mib"] = total.value >> 20

    ctx = ctypes.c_void_p()
    try:
        cuda.check(cuda.ctx_create(ctypes.byref(ctx), 0, handle), "cuCtxCreate")
    except CudaError as exc:
        dev["checks"]["context"] = failed(exc)
        return dev
    dev["checks"]["context"] = ok()

    try:
        free, total_now = ctypes.c_size_t(), ctypes.c_size_t()
        if cuda.mem_info(ctypes.byref(free), ctypes.byref(total_now)) == 0:
            dev["memory_free_mib"] = free.value >> 20

        nbytes = alloc_mib << 20
        ptr = ctypes.c_void_p()
        try:
            cuda.check(cuda.mem_alloc(ctypes.byref(ptr), nbytes), "cuMemAlloc")
            dev["checks"]["allocate"] = ok("%d MiB" % alloc_mib)
        except CudaError as exc:
            dev["checks"]["allocate"] = failed(exc)
            return dev

        try:
            payload = bytes(range(256)) * 4
            buf = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
            back = (ctypes.c_ubyte * len(payload))()
            cuda.check(cuda.memcpy_h2d(ptr, buf, len(payload)), "cuMemcpyHtoD")
            cuda.check(cuda.memcpy_d2h(back, ptr, len(payload)), "cuMemcpyDtoH")
            if bytes(back) != payload:
                raise CudaError("data came back altered")
            dev["checks"]["memcpy"] = ok()
        except CudaError as exc:
            dev["checks"]["memcpy"] = failed(exc)

        # Device-side fill: work the GPU itself performs, no JIT involved.
        try:
            words = 4096
            cuda.check(cuda.memset_d32(ptr, 0xA5A5A5A5, words), "cuMemsetD32")
            cuda.check(cuda.ctx_sync(), "cuCtxSynchronize")
            back32 = (ctypes.c_uint * words)()
            cuda.check(cuda.memcpy_d2h(back32, ptr, words * 4), "cuMemcpyDtoH")
            if any(v != 0xA5A5A5A5 for v in back32):
                raise CudaError("device memset did not take effect")
            dev["checks"]["device_memset"] = ok()
        except CudaError as exc:
            dev["checks"]["device_memset"] = failed(exc)

        cuda.mem_free(ptr)

        version = ctypes.c_int()
        cuda.driver_version(ctypes.byref(version))
        try:
            dev["checks"]["kernel_launch"] = ok(
                check_kernel_launch(
                    cuda, major.value, minor.value, ptx_isa_version(version.value)
                )
            )
        except CudaError as exc:
            dev["checks"]["kernel_launch"] = failed(exc)
    finally:
        cuda.ctx_destroy(ctx)

    return dev


def probe_cuda(alloc_mib):
    lib = load("libcuda.so.1")
    if lib is None:
        return {"available": False, "error": "libcuda.so.1 not found"}

    try:
        cuda = Cuda(lib)
    except AttributeError as exc:
        # A driver too old to export something the checker uses.
        return {"available": False, "error": "libcuda.so.1 is missing %s" % exc}

    result = {"available": True, "devices": []}
    try:
        cuda.check(cuda.init(0), "cuInit")
    except CudaError as exc:
        result["available"] = False
        result["error"] = str(exc)
        return result

    version = ctypes.c_int()
    cuda.driver_version(ctypes.byref(version))
    result["driver_api"] = "{}.{}".format(
        version.value // 1000, (version.value % 1000) // 10
    )

    count = ctypes.c_int()
    try:
        cuda.check(cuda.device_count(ctypes.byref(count)), "cuDeviceGetCount")
    except CudaError as exc:
        result["error"] = str(exc)
        return result

    for i in range(count.value):
        try:
            result["devices"].append(probe_device(cuda, i, alloc_mib))
        except CudaError as exc:
            result["devices"].append({"index": i, "error": str(exc)})
    return result


# ── reporting ─────────────────────────────────────────────────────

CHECK_LABELS = {
    "context": "context create",
    "allocate": "device allocation",
    "memcpy": "host<->device copy",
    "device_memset": "device-side memset",
    "kernel_launch": "kernel launch",
}


def collect(alloc_mib):
    report = {"driver": probe_driver(), "cuda": probe_cuda(alloc_mib)}

    nvml_lib = load("libnvidia-ml.so.1")
    telemetry = Nvml(nvml_lib).telemetry() if nvml_lib else {}
    for dev in report["cuda"].get("devices", []):
        if dev["index"] in telemetry:
            dev["telemetry"] = telemetry[dev["index"]]

    devices = report["cuda"].get("devices", [])
    present = bool(report["driver"]["loaded"] or devices)
    failures = [
        "GPU {} {}: {}".format(
            dev["index"], CHECK_LABELS.get(name, name), check["detail"]
        )
        for dev in devices
        for name, check in dev.get("checks", {}).items()
        if not check["ok"]
    ] + [
        "GPU {}: {}".format(dev["index"], dev["error"])
        for dev in devices
        if "error" in dev
    ]

    report["present"] = present
    report["usable"] = bool(devices) and not failures
    report["failures"] = failures
    return report


def render(report, out):
    driver = report["driver"]
    cuda = report["cuda"]

    if not report["present"]:
        print("No NVIDIA GPU visible here.", file=out)
        print("  kernel driver: not loaded (%s absent)" % PROC_VERSION, file=out)
        if not cuda.get("available"):
            print("  CUDA driver:   %s" % cuda.get("error", "unavailable"), file=out)
        print(file=out)
        print(
            "If the host has a GPU, start the container with `yolo --nvidia`\n"
            "(needs nvidia-container-toolkit and a CDI spec on the host).",
            file=out,
        )
        return

    print(
        "kernel driver:   %s"
        % (driver["version"] or "loaded, version unknown"),
        file=out,
    )
    if driver["device_nodes"]:
        print("device nodes:    %s" % ", ".join(driver["device_nodes"]), file=out)
    if cuda.get("driver_api"):
        print("CUDA driver API: %s" % cuda["driver_api"], file=out)
    if not cuda.get("available"):
        print("CUDA driver API: %s" % cuda.get("error", "unavailable"), file=out)

    for dev in cuda.get("devices", []):
        print(file=out)
        print("GPU %d: %s" % (dev["index"], dev.get("name", "?")), file=out)
        if "error" in dev:
            print("  error: %s" % dev["error"], file=out)
            continue
        print(
            "  compute capability  %s (%d SMs)"
            % (dev["compute_capability"], dev["multiprocessors"]),
            file=out,
        )
        mem = "%d MiB total" % dev["memory_total_mib"]
        if "memory_free_mib" in dev:
            mem += ", %d MiB free" % dev["memory_free_mib"]
        print("  memory              %s" % mem, file=out)
        tel = dev.get("telemetry", {})
        if tel:
            bits = []
            if "utilization_pct" in tel:
                bits.append("%d%% busy" % tel["utilization_pct"])
            if "temperature_c" in tel:
                bits.append("%d C" % tel["temperature_c"])
            if "power_w" in tel:
                bits.append("%g W" % tel["power_w"])
            print("  telemetry           %s" % ", ".join(bits), file=out)
        for name, label in CHECK_LABELS.items():
            if name not in dev["checks"]:
                continue
            check = dev["checks"][name]
            if check["ok"]:
                suffix = " (%s)" % check["detail"] if check["detail"] else ""
                print("  %-19s OK%s" % (label, suffix), file=out)
            else:
                print("  %-19s FAILED -- %s" % (label, check["detail"]), file=out)

    print(file=out)
    if report["usable"]:
        print("GPU compute is available.", file=out)
    elif not cuda.get("devices"):
        print(
            "Driver is loaded but no CUDA device is usable: %s"
            % cuda.get("error", "no devices enumerated"),
            file=out,
        )
    else:
        print("GPU is present but not fully usable.", file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check NVIDIA GPU access without nvidia-smi.",
        epilog="Exit codes: 0 usable, 1 present but broken, 2 no GPU here.",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the full report as JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print nothing; report via exit code"
    )
    parser.add_argument(
        "--alloc-mib",
        type=int,
        default=64,
        metavar="N",
        help="size of the test allocation (default: 64)",
    )
    args = parser.parse_args(argv)

    report = collect(args.alloc_mib)

    if args.quiet:
        pass
    elif args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        render(report, sys.stdout)

    if not report["present"]:
        return 2
    return 0 if report["usable"] else 1


if __name__ == "__main__":
    sys.exit(main())

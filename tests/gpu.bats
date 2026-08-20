#!/usr/bin/env bats
#
# Tests for tools/gpu-check.py.
#
# The checker is hardware-dependent by nature, so the file is split in three:
# tests that hold everywhere, tests that stub the driver away so the "no GPU"
# path is covered even on a GPU host, and tests that need real hardware and
# skip without it.  `bats tests/` is therefore safe to run anywhere.

load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'
load 'test_helper/common'

# ── always ────────────────────────────────────────────────────────

@test "gpu-check: is executable and stdlib-only" {
    require_python
    [ -x "$GPU_CHECK_BIN" ]
    # Compile into the test tmpdir so the repo never collects a __pycache__.
    run python3 -c 'import py_compile, sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)' \
        "$GPU_CHECK_BIN" "$BATS_TEST_TMPDIR/gpu-check.pyc"
    assert_success
    # Anything beyond the standard library would defeat the point: the script
    # has to run in a bare container with no pip packages installed. Check the
    # imports by AST rather than by grep, which differs across GNU/BSD.
    run python3 -c '
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
allowed = {"argparse", "ctypes", "glob", "json", "os", "sys"}
used = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        used.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        used.add(node.module.split(".")[0])
extra = used - allowed
assert not extra, "non-stdlib or unexpected imports: %s" % sorted(extra)
' "$GPU_CHECK_BIN"
    assert_success
}

@test "gpu-check: --help documents the exit codes" {
    require_python
    run_gpu_check --help
    assert_success
    assert_output --partial "--json"
    assert_output --partial "Exit codes"
}

@test "gpu-check: --json is parseable and carries the expected keys" {
    require_python
    run_gpu_check --json
    run python3 -c '
import json, sys
r = json.load(sys.stdin)
for key in ("driver", "cuda", "present", "usable", "failures"):
    assert key in r, "missing key: " + key
assert isinstance(r["present"], bool)
assert isinstance(r["usable"], bool)
assert isinstance(r["failures"], list)
' <<< "$output"
    assert_success
}

@test "gpu-check: exit status reflects GPU presence" {
    require_python
    run_gpu_check --quiet
    if has_gpu; then
        # 0 = usable, 1 = present but a check failed. A GPU host that reports 1
        # has genuinely broken passthrough, so failing here is the point.
        assert_success
    else
        assert_equal "$status" 2
    fi
}

@test "gpu-check: --quiet prints nothing" {
    require_python
    run_gpu_check --quiet
    assert_output ""
}

# ── no-GPU path, stubbed so it runs on GPU hosts too ──────────────

@test "gpu-check: reports exit 2 and advice when no driver is visible" {
    require_python
    cat > "$BATS_TEST_TMPDIR/stub.py" << EOF
import importlib.util, sys

spec = importlib.util.spec_from_file_location("gpu_check", "$GPU_CHECK_BIN")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Hide every route to a GPU: no driver libraries, no /proc, no device nodes.
mod.load = lambda name: None
mod.PROC_VERSION = "/nonexistent/driver/version"
mod.PROC_GPUS = "/nonexistent/driver/gpus"
mod.glob.glob = lambda pattern: []

sys.exit(mod.main([]))
EOF
    run python3 "$BATS_TEST_TMPDIR/stub.py"
    assert_equal "$status" 2
    assert_output --partial "No NVIDIA GPU visible here"
    assert_output --partial "yolo --nvidia"
}

# ── real hardware ─────────────────────────────────────────────────

@test "gpu-check: reports the kernel driver version and a device" {
    require_python
    require_gpu
    run_gpu_check
    assert_success
    assert_output --partial "kernel driver:"
    assert_output --partial "CUDA driver API:"
    assert_output --regexp 'GPU 0: '
}

@test "gpu-check: every compute check passes on real hardware" {
    require_python
    require_gpu
    run_gpu_check --json
    assert_success
    run python3 -c '
import json, sys
r = json.load(sys.stdin)
assert r["present"] and r["usable"], r["failures"]
assert r["driver"]["loaded"], "kernel driver not reported as loaded"
assert r["cuda"]["devices"], "no CUDA devices enumerated"
for dev in r["cuda"]["devices"]:
    for name in ("context", "allocate", "memcpy", "device_memset", "kernel_launch"):
        check = dev["checks"].get(name)
        assert check, "check not run: " + name
        assert check["ok"], "%s failed: %s" % (name, check["detail"])
' <<< "$output"
    assert_success
}

@test "gpu-check: --alloc-mib sizes the test allocation" {
    require_python
    require_gpu
    run_gpu_check --alloc-mib 8
    assert_success
    assert_output --partial "device allocation   OK (8 MiB)"
}

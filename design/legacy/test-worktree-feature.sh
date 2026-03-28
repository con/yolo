#!/bin/bash
# Test script for --worktree feature and argument parsing

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
YOLO="$SCRIPT_DIR/bin/yolo"

pass=0
fail=0

test_pass() {
    echo "✓ PASS: $1"
    ((pass++))
}

test_fail() {
    echo "✗ FAIL: $1"
    ((fail++))
}

echo "=== Testing script syntax ==="

if bash -n "$YOLO"; then
    test_pass "bin/yolo has valid bash syntax"
else
    test_fail "bin/yolo has valid bash syntax"
fi

echo ""
echo "=== Testing --worktree argument parsing ==="

# Test: Invalid worktree value rejected
if $YOLO --worktree=invalid 2>&1 | grep -q "Invalid --worktree value"; then
    test_pass "Invalid --worktree value rejected"
else
    test_fail "Invalid --worktree value rejected"
fi

# Test: --worktree=create (bare) rejected with helpful message
if $YOLO --worktree=create 2>&1 | grep -q "requires a branch name"; then
    test_pass "--worktree=create (bare) rejected with helpful message"
else
    test_fail "--worktree=create (bare) rejected with helpful message"
fi

# Test: --worktree=create:branch passes validation (exits with different error, not "Invalid")
output=$(timeout 1 $YOLO --worktree=create:test-branch 2>&1 </dev/null || true)
if echo "$output" | grep -q "Invalid --worktree value"; then
    test_fail "--worktree=create:branch accepted"
else
    test_pass "--worktree=create:branch accepted"
fi
# Cleanup in case the worktree was created
git worktree remove "$(dirname "$SCRIPT_DIR")/test-branch" 2>/dev/null || true
git branch -d test-branch 2>/dev/null || true

# Test: Each valid mode passes validation (exits with different error, not "Invalid")
for mode in ask bind skip error; do
    output=$(timeout 1 $YOLO --worktree=$mode 2>&1 </dev/null || true)
    if echo "$output" | grep -q "Invalid --worktree value"; then
        test_fail "--worktree=$mode accepted"
    else
        test_pass "--worktree=$mode accepted"
    fi
done

echo ""
echo "=== Testing worktree detection ==="

# Check if we're in a worktree
if [ -f "$SCRIPT_DIR/.git" ]; then
    test_pass "Current directory is a git worktree (.git is a file)"
    is_worktree=1

    # --worktree=error should fail in a worktree
    if $YOLO --worktree=error 2>&1 | grep -q "Running in a git worktree is not allowed"; then
        test_pass "--worktree=error exits with error in worktree"
    else
        test_fail "--worktree=error exits with error in worktree"
    fi
else
    echo "Note: Current directory is NOT a worktree (.git is a directory)"
    is_worktree=0

    # Create a temporary worktree to test detection
    echo "Creating temporary worktree for testing..."
    temp_dir=$(mktemp -d)
    worktree_dir="$temp_dir/test-worktree"

    if git worktree add "$worktree_dir" HEAD 2>/dev/null; then
        test_pass "Created temporary worktree"

        # Test --worktree=error in the temporary worktree
        cd "$worktree_dir"
        if "$YOLO" --worktree=error 2>&1 | grep -q "Running in a git worktree is not allowed"; then
            test_pass "--worktree=error exits with error in worktree"
        else
            test_fail "--worktree=error exits with error in worktree"
        fi
        cd "$SCRIPT_DIR"

        # Cleanup
        git worktree remove "$worktree_dir" 2>/dev/null || rm -rf "$worktree_dir"
        rmdir "$temp_dir" 2>/dev/null || true
    else
        echo "Could not create temporary worktree, skipping worktree detection tests"
    fi
fi

echo ""
echo "=== Testing --entrypoint option ==="

# Test --entrypoint with space syntax (just parsing, will timeout before podman)
output=$(timeout 1 $YOLO --worktree=error --entrypoint testcmd 2>&1 </dev/null || true)
if echo "$output" | grep -q "Invalid"; then
    test_fail "--entrypoint testcmd parsing"
else
    test_pass "--entrypoint testcmd parsing"
fi

# Test --entrypoint with = syntax
output=$(timeout 1 $YOLO --worktree=error --entrypoint=testcmd 2>&1 </dev/null || true)
if echo "$output" | grep -q "Invalid"; then
    test_fail "--entrypoint=testcmd parsing"
else
    test_pass "--entrypoint=testcmd parsing"
fi

echo ""
echo "=== Testing combined options ==="

# Test combined options by checking for parse errors only (not running container)
# We grep for our custom error messages - if none appear, parsing succeeded
output=$(timeout 1 $YOLO --worktree=invalid --entrypoint bash --anonymized-paths 2>&1 </dev/null || true)
if echo "$output" | grep -q "Invalid --worktree value"; then
    # Good - it caught the invalid value, meaning it parsed all args
    test_pass "Combined options parsing"
else
    test_fail "Combined options parsing"
fi

echo ""
echo "=== Integration tests (requires container) ==="

# Check if podman is available and image exists
if command -v podman &>/dev/null && podman image exists con-bomination-claude-code 2>/dev/null; then
    echo "Container available, running integration tests..."

    # Determine worktree flag to use (ok if in worktree, omit otherwise)
    if [ "$is_worktree" -eq 1 ]; then
        wt_flag="--worktree=skip"
    else
        wt_flag=""
    fi

    # Test: --entrypoint echo works
    if timeout 30 $YOLO $wt_flag --entrypoint echo -- "integration test" 2>&1 | grep -q "integration test"; then
        test_pass "--entrypoint echo works"
    else
        test_fail "--entrypoint echo works"
    fi

    # Test: --entrypoint bash works
    if timeout 30 $YOLO $wt_flag --entrypoint bash -- -c "echo hello" 2>&1 | grep -q "hello"; then
        test_pass "--entrypoint bash works"
    else
        test_fail "--entrypoint bash works"
    fi
else
    echo "Skipping integration tests (podman or image not available)"
fi

echo ""
echo "=== Summary ==="
echo "Passed: $pass"
echo "Failed: $fail"

if [ "$fail" -gt 0 ]; then
    exit 1
fi

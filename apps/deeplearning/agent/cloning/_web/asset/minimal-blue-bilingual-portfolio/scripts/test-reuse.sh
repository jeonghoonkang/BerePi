#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source_dir=$(realpath -e -- "$script_dir/../assets/site")
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

# Invoke from another working directory; include spaces and missing parents.
cd -- "$test_dir"
bash "$script_dir/reuse.sh" 'parent folder/my portfolio'
diff -qr -- "$source_dir" "$test_dir/parent folder/my portfolio"
printf 'sentinel\n' > 'parent folder/my portfolio/keep.txt'
if bash "$script_dir/reuse.sh" 'parent folder/my portfolio' > refusal.log 2>&1; then
    printf 'FAIL: existing directory was accepted\n' >&2
    exit 1
fi
[[ $(cat 'parent folder/my portfolio/keep.txt') == sentinel ]]
if bash "$script_dir/reuse.sh" > usage.log 2>&1; then
    printf 'FAIL: missing argument was accepted\n' >&2
    exit 1
fi
ln -s -- "$test_dir/missing" "$test_dir/dangling-link"
if bash "$script_dir/reuse.sh" "$test_dir/dangling-link" > symlink.log 2>&1; then
    printf 'FAIL: existing symlink was accepted\n' >&2
    exit 1
fi
if bash "$script_dir/reuse.sh" "$source_dir/nested-test-output" > nested.log 2>&1; then
    printf 'FAIL: destination inside template was accepted\n' >&2
    exit 1
fi
printf 'PASS: copy contents, relative paths, spaces, overwrite protection, argument validation, symlink and nested destination rejection\n'

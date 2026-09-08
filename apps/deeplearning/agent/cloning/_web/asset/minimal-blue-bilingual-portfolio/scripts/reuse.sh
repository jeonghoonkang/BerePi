#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || -z "$1" ]]; then
    printf 'Usage: bash %s <new-destination-directory>\n' "$0" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source_dir=$(realpath -e -- "$script_dir/../assets/site")
if [[ -L "$1" ]]; then
    printf 'Destination already exists as a symlink: %s\n' "$1" >&2
    exit 1
fi
target=$(realpath -m -- "$1")

if [[ -e "$target" || -L "$target" ]]; then
    printf 'Destination already exists; choose a new directory: %s\n' "$target" >&2
    exit 1
fi
case "$target/" in
    "$source_dir/"*)
        printf 'Destination must be outside the site template: %s\n' "$target" >&2
        exit 1 ;;
esac
if [[ ! -f "$source_dir/index.html" ]]; then
    printf 'Site template is missing: %s\n' "$source_dir" >&2
    exit 1
fi

mkdir -p -- "$(dirname -- "$target")"
# An exclusive mkdir also rejects a destination created since the earlier check.
mkdir -- "$target"
cp -R -- "$source_dir/." "$target/"
printf 'Created: %s\nOpen: %s/index.html\n' "$target" "$target"

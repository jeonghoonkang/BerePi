import argparse
import os
import subprocess
from typing import Dict, Tuple


def run_rsync(src: str, dest: str) -> None:
    """Copy *src* directory to *dest* using rsync."""
    subprocess.run([
        "rsync",
        "-av",
        f"{src}/",
        dest,
    ], check=True)


def scan_directory(path: str) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """Return per-directory statistics and per-file sizes."""
    dir_stats: Dict[str, Dict[str, int]] = {}
    file_stats: Dict[str, int] = {}
    for root, dirs, files in os.walk(path):
        rel_dir = os.path.relpath(root, path)
        total_size = 0
        for name in files:
            file_path = os.path.join(root, name)
            if os.path.islink(file_path):
                continue
            try:
                size = os.path.getsize(file_path)
            except OSError:
                size = 0
            total_size += size
            file_stats[os.path.relpath(file_path, path)] = size
        dir_stats[rel_dir] = {"size": total_size, "count": len(files)}
    return dir_stats, file_stats


def compare_stats(
    src_info: Tuple[Dict[str, Dict[str, int]], Dict[str, int]],
    dest_info: Tuple[Dict[str, Dict[str, int]], Dict[str, int]],
) -> Tuple[list, list]:
    """Compare directory and file statistics."""
    src_dirs, src_files = src_info
    dest_dirs, dest_files = dest_info

    diff_dirs = []
    all_dirs = set(src_dirs.keys()) | set(dest_dirs.keys())
    for d in sorted(all_dirs):
        s = src_dirs.get(d, {"size": 0, "count": 0})
        t = dest_dirs.get(d, {"size": 0, "count": 0})
        if s != t:
            diff_dirs.append((d, s, t))

    diff_files = []
    all_files = set(src_files.keys()) | set(dest_files.keys())
    for f in sorted(all_files):
        s_size = src_files.get(f)
        t_size = dest_files.get(f)
        if s_size != t_size:
            diff_files.append((f, s_size, t_size))
    return diff_dirs, diff_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy directory with rsync and compare statistics",
    )
    parser.add_argument("src", help="source directory")
    parser.add_argument("dest", help="destination directory")
    args = parser.parse_args()

    run_rsync(args.src, args.dest)

    src_info = scan_directory(args.src)
    dest_info = scan_directory(args.dest)

    diff_dirs, diff_files = compare_stats(src_info, dest_info)

    if diff_dirs:
        print("\nDirectories with differences:")
        for path, src_stat, dest_stat in diff_dirs:
            print(
                f"{path}: src size={src_stat['size']}B files={src_stat['count']}, "
                f"dest size={dest_stat['size']}B files={dest_stat['count']}"
            )
    else:
        print("\nAll directories match in size and file count.")

    if diff_files:
        print("\nFiles with differences:")
        for path, src_size, dest_size in diff_files:
            print(f"{path}: src={src_size}B dest={dest_size}B")
    else:
        print("\nAll files match in size.")


if __name__ == "__main__":
    main()

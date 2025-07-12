#Author : https://github.com/jeonghoonkang 

import os
import hashlib
import argparse
from collections import defaultdict
import datetime


def compute_hash(path, chunk_size=8192):
    """Return the SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()

def gather_file_info(root_dir, exts):
    """Return a list of (path, size) tuples for files with given extensions."""
    results = []
    for base, _, files in os.walk(root_dir):
        for name in files:
            if not exts or os.path.splitext(name)[1].lstrip('.').lower() in exts:
                path = os.path.join(base, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                results.append((path, size))
    return results

def find_duplicates(root_dir, exts):
    print (f"Searching in {root_dir} for files with extensions: {exts}")

    files_by_size = defaultdict(list)
    
    print("Collecting files by size...", "end of files_by_size" )
    
    for base, _, files in os.walk(root_dir):
        for name in files:
            if not exts or os.path.splitext(name)[1].lstrip('.').lower() in exts:
                path = os.path.join(base, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                files_by_size[size].append(path)

    duplicates = defaultdict(list)

    print("items in files_by_size:", len(files_by_size))
    file_cnt = 0

    for size, paths in files_by_size.items():
        file_cnt += 1
        if len(paths) < 2:
            continue
        hashes = defaultdict(list)
        for path in paths:
            try:
                h = compute_hash(path)
            except OSError:
                continue
            hashes[h].append(path)
        for h, hp in hashes.items():
            if len(hp) > 1:
                duplicates[h].extend(hp)

        if file_cnt == 1:
            print(f"time : {file_cnt}", datetime.datetime.now())
        if file_cnt == 2 :
            print(f"time : {file_cnt}", datetime.datetime.now()) 
        if file_cnt == 3:
            print(f"time : {file_cnt}", datetime.datetime.now())
            
        if file_cnt % 4000 == 0:
            print(f"Processed {file_cnt} file sizes, found {len(duplicates)} potential duplicates so far...")
    return duplicates

def group_lines_by_size(file_path):
    """Rewrite the file so lines with the same leading size are consecutive."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    def get_size(line):
        try:
            return int(line.split("\t", 1)[0])
        except (ValueError, IndexError):
            return -1

    lines.sort(key=get_size)
    with open(file_path, "w", encoding="utf-8") as f:
        current_group = []
        current_size = None

        for line in lines:
            size = get_size(line)
            if current_size is None:
                current_size = size
            if size != current_size:
                for item in current_group:
                    f.write(item + "\n")
                if len(current_group) > 1:
                    f.write("\n")
                current_group = [line]
                current_size = size
            else:
                current_group.append(line)

        # flush last group
        for item in current_group:
            f.write(item + "\n")
        if len(current_group) > 1:
            f.write("\n")

    
def main():
    parser = argparse.ArgumentParser(description="Find duplicate CSV/JSON files")
    parser.add_argument("directory", help="Root directory to search")
    parser.add_argument("--exts", default="csv,json", help="Comma separated list of extensions")
    parser.add_argument(
        "--output",
        default="file_info.txt",
        help="Path to the output text file",
    )

    parser.add_argument(
        "--group",
        metavar="TXT",
        help="Group lines in an existing info file by size",
    )

    args = parser.parse_args()
    exts = {e.lower() for e in args.exts.split(',') if e}

    if args.group:
        group_lines_by_size(args.group)
        print(f"Grouped lines by size in {args.group}")
        return

    info = gather_file_info(args.directory, exts)

    with open(args.output, "w", encoding="utf-8") as f:
        for path, size in info:
            f.write(f"{size}\t{path}\n")

    print(f"Wrote info for {len(info)} files to {args.output}")



    #duplicates = find_duplicates(args.directory, exts)
    # if not duplicates:
    #     print("No duplicates found")
    # else:
    #     print("Duplicate files:")
    #     for h, paths in duplicates.items():
    #         print(f"Hash {h}:")
    #         for p in paths:
    #             print(f"  {p}")


if __name__ == "__main__":
    main()
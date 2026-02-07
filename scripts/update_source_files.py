import argparse
from pathlib import Path
from typing import Iterable
from rich.progress import Progress, BarColumn, TextColumn



def replace_in_file(file_path: Path, old_text: str, new_text: str) -> bool:
    """Replace occurrences of old_text with new_text in the given file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # skip files that cannot be decoded
        return False
    updated = content.replace(old_text, new_text)
    if updated != content:
        file_path.write_text(updated, encoding="utf-8")
        return True
    return False


def gather_files(directory: Path) -> Iterable[Path]:
    """Yield all file paths under the given directory."""
    for path in directory.rglob("*"):
        if path.is_file():
            yield path


def process_directory(directory: Path, old_text: str, new_text: str):
    files = list(gather_files(directory))
    total = len(files)
    if total == 0:
        print("No files found to process.")
        return

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
    )
    with progress:
        task = progress.add_task("Processing files", total=total)
        for path in files:
            if replace_in_file(path, old_text, new_text):
                progress.console.print(f"Updated {path}")
            progress.update(task, advance=1)



def main():
    parser = argparse.ArgumentParser(
        description="Replace text in all text files within the given directory.")
    parser.add_argument("directory", type=Path, help="Root directory to traverse")
    parser.add_argument("old_text", help="Text or date to search for")
    parser.add_argument("new_text", help="Text or date to replace with")
    args = parser.parse_args()

    if not args.directory.is_dir():
        parser.error(f"{args.directory} is not a directory")

    process_directory(args.directory, args.old_text, args.new_text)


if __name__ == "__main__":
    main()

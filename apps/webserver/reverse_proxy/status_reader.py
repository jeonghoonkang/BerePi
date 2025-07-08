import argparse
import getpass
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Show status file content with a password prompt"
    )
    parser.add_argument("--file", default="status.txt", help="path to status file")
    parser.add_argument(
        "--expected-pass",
        default="secret",
        help="password required to view the file",
    )
    args = parser.parse_args()

    entered = getpass.getpass("Password: ")
    if entered != args.expected_pass:
        print("Access denied")
        sys.exit(1)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            print(f.read())
    except FileNotFoundError:
        print(f"File not found: {args.file}")
        sys.exit(1)


if __name__ == "__main__":
    main()

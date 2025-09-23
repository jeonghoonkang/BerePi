import subprocess
import sys
from pathlib import Path


def main() -> int:
    here = Path(__file__).resolve()
    main_py = here.with_name("main.py")
    if not main_py.exists():
        print("FAILED: main.py not found next to test.py")
        return 1

    # Run the existing CLI in minimal connect mode to reuse config handling
    proc = subprocess.run(
        [sys.executable, str(main_py), "connect"],
        capture_output=True,
        text=True,
    )

    # Relay output to caller
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip(), file=sys.stderr)

    # Determine success from standardized output
    out = (proc.stdout or "") + (proc.stderr or "")
    if "SUCCESS: Connected to MinIO." in out:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())


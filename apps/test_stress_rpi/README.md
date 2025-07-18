# Raspberry Pi Stress Test

This script runs a CPU and disk stress test for 15 minutes and prints
average CPU usage and total disk I/O during the test. While running,
it shows a progress bar using the Rich package.

## Usage

```bash
python3 stress_test.py
```

Install the `rich` package before running the script:

```bash
pip install rich
```

The script spawns worker processes equal to the number of CPU cores and
continuously writes to a temporary file to generate disk activity. After
15 minutes it reports average CPU utilization and disk read/write totals.

# Raspberry Pi Stress Test

This script runs a CPU and disk stress test for 15 minutes and prints
average CPU usage and total disk I/O during the test.

## Usage

```bash
python3 stress_test.py
```

The script does not require additional dependencies. It spawns worker
processes equal to the number of CPU cores and continuously writes to a
temporary file to generate disk activity. After 15 minutes it reports
average CPU utilization and disk read/write totals.

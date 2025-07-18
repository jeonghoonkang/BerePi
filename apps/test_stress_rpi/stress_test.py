import os
import sys
import time
import threading
import multiprocessing
from rich.progress import Progress, BarColumn, TimeRemainingColumn, TextColumn


def read_cpu_times():
    """Read total and idle CPU times from /proc/stat."""
    with open("/proc/stat", "r") as f:
        for line in f:
            if line.startswith("cpu "):
                fields = [int(x) for x in line.split()[1:8]]
                total = sum(fields)
                idle = fields[3] + fields[4]
                return total, idle
    return 0, 0


def read_disk_stats():
    """Read total read and write sectors from /proc/diskstats."""
    total_read = 0
    total_write = 0
    with open("/proc/diskstats", "r") as f:
        for line in f:
            parts = line.split()
            # sectors read is column 5, sectors written is column 9
            if len(parts) >= 10:
                total_read += int(parts[5])
                total_write += int(parts[9])
    return total_read, total_write


def cpu_worker(stop_event):
    x = 0
    while not stop_event.is_set():
        x = (x * x + 1) % 1000000007


def disk_worker(stop_event, filename):
    block = os.urandom(1024 * 1024)  # 1MB
    with open(filename, "wb") as f:
        while not stop_event.is_set():
            f.write(block)
            f.flush()
            os.fsync(f.fileno())
    os.remove(filename)


def main(duration=900):
    start_total, start_idle = read_cpu_times()
    start_read, start_write = read_disk_stats()

    stop_event = multiprocessing.Event()
    cpu_processes = []
    for _ in range(os.cpu_count() or 1):
        p = multiprocessing.Process(target=cpu_worker, args=(stop_event,))
        p.start()
        cpu_processes.append(p)

    disk_thread = threading.Thread(target=disk_worker, args=(stop_event, "stress_test_file.dat"))
    disk_thread.start()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Running stress test", total=duration)
        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break
            progress.update(task, completed=elapsed)
            time.sleep(1)
        progress.update(task, completed=duration)


    stop_event.set()
    disk_thread.join()
    for p in cpu_processes:
        p.join()

    end_total, end_idle = read_cpu_times()
    end_read, end_write = read_disk_stats()

    cpu_usage = 0.0
    if end_total - start_total > 0:
        cpu_usage = 100.0 * (1 - (end_idle - start_idle) / (end_total - start_total))

    sector_size = 512  # bytes
    read_bytes = (end_read - start_read) * sector_size
    write_bytes = (end_write - start_write) * sector_size

    read_mb = read_bytes / (1024 * 1024)
    write_mb = write_bytes / (1024 * 1024)

    print("\n===== Stress Test Summary =====")
    print(f"Average CPU usage : {cpu_usage:.2f}%")
    print(f"Disk read         : {read_mb:.2f} MB")
    print(f"Disk write        : {write_mb:.2f} MB")


if __name__ == "__main__":
    dur = 900
    if len(sys.argv) > 1:
        try:
            dur = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration '{sys.argv[1]}', using default 900s")
    try:
        main(dur)
    except KeyboardInterrupt:
        pass

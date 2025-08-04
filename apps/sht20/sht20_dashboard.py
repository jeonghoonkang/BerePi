import os
import subprocess
import time
import shutil
import urllib.request
import urllib.parse


INFLUX_HOST = "localhost"
INFLUX_PORT = 8086
INFLUX_USER = os.environ.get("INFLUX_USER", "admin")
INFLUX_PASS = os.environ.get("INFLUX_PASS", "admin")
INFLUX_DB = "sht20"
INFLUX_MEASUREMENT = "temperature"


def start_influxdb():
    """Start an InfluxDB server if one is not already running."""
    if subprocess.call(["pgrep", "influxd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return None
    if not shutil.which("influxd"):
        print("InfluxDB binary not found")
        return None
    try:
        proc = subprocess.Popen(
            ["influxd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return proc
    except Exception as exc:  # pragma: no cover
        print("Failed to start InfluxDB:", exc)
        return None


def fetch_chart_png(outfile="temperature.png"):
    """Request a 48-hour temperature graph from InfluxDB and save it."""
    query = (
        f'SELECT mean("value") FROM "{INFLUX_MEASUREMENT}" '
        f'WHERE time > now() - 48h GROUP BY time(1h)'
    )
    params = urllib.parse.urlencode(
        {
            "db": INFLUX_DB,
            "u": INFLUX_USER,
            "p": INFLUX_PASS,
            "q": query,
            "format": "png",
        }
    )
    url = f"http://{INFLUX_HOST}:{INFLUX_PORT}/render?{params}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"InfluxDB render failed: HTTP {resp.status}")
        with open(outfile, "wb") as fh:
            fh.write(resp.read())
    return outfile


def fetch_and_send():
    """Fetch the chart PNG and send it via telegram-send."""
    outfile = "temperature.png"
    try:
        fetch_chart_png(outfile)

        subprocess.run(["telegram-send", "-f", outfile], check=False)
    except errors.BrowserError as exc:  # pragma: no cover
        print("Capture/send failed: headless Chrome crashed:", exc)
    except Exception as exc:  # pragma: no cover
        print("Capture/send failed:", exc)



if __name__ == "__main__":
    influx_proc = start_influxdb()
    if influx_proc is not None:
        import atexit

        atexit.register(influx_proc.terminate)

    while True:
        fetch_and_send()
        time.sleep(12 * 3600)



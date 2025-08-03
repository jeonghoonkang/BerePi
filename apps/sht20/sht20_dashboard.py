import os
import socket
import subprocess
import time
from threading import Thread
import shutil

from flask import Flask, render_template_string
from influxdb import InfluxDBClient

PORT = 5001
INFLUX_HOST = "localhost"
INFLUX_PORT = 8086
INFLUX_USER = os.environ.get("INFLUX_USER", "admin")
INFLUX_PASS = os.environ.get("INFLUX_PASS", "admin")
INFLUX_DB = "sht20"
INFLUX_MEASUREMENT = "temperature"

app = Flask(__name__)


def get_ip_address():
    """Return the host's primary IP address."""
    ip = "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    return ip


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


def query_week(start_days, end_days):
    """Query a week's worth of readings from InfluxDB."""
    query = (
        f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" '
        f"WHERE time >= now() - {start_days}d AND time < now() - {end_days}d"
    )
    points = []
    try:
        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASS,
            database=INFLUX_DB,
        )
        result = client.query(query)
        for pt in result.get_points():
            points.append({"time": pt["time"], "value": pt["value"]})
    except Exception as exc:  # pragma: no cover
        print("InfluxDB query error:", exc)
    return points


def fetch_weeks():
    """Return data for four weeks, newest first."""
    weeks = []
    for i in range(4):
        start = 7 * (i + 1)
        end = 7 * i
        weeks.append(query_week(start, end))
    return weeks


@app.route("/")
def index():
    weeks = fetch_weeks()
    return render_template_string(
        """
        <html>
        <head>
            <title>SHT20 Charts</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <h1>Monthly temperature overview</h1>
            {% for w in range(4) %}
            <h2>Week {{ loop.index }}</h2>
            <canvas id="chart{{loop.index}}" width="400" height="200"></canvas>
            {% endfor %}
            <script>
            const weeks = {{ weeks|tojson }};
            weeks.forEach((wk, idx) => {
                const ctx = document.getElementById('chart'+(idx+1)).getContext('2d');
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: wk.map(p => p.time),
                        datasets: [{ label: 'Temperature', data: wk.map(p => p.value), borderColor: 'blue', fill: false }]
                    },
                    options: { scales: { x: { ticks: { maxTicksLimit: 6 } } } }
                });
            });
            window.status = 'ready';
            </script>
        </body>
        </html>
        """,
        weeks=weeks,
    )


def capture_and_send(url, outfile="dashboard.jpg"):
    """Capture the given URL to an image and send via telegram-send."""
    try:
        import imgkit

        options = {
            "javascript-delay": 2000,
            "enable-local-file-access": "",
            "window-status": "ready",
            "no-stop-slow-scripts": "",
        }
        imgkit.from_url(url, outfile, options=options)
        subprocess.run(["telegram-send", "-f", outfile], check=False)
    except Exception as exc:  # pragma: no cover
        print("Capture/send failed:", exc)


if __name__ == "__main__":
    import shutil

    influx_proc = start_influxdb()
    if influx_proc is not None:
        import atexit
        atexit.register(influx_proc.terminate)

    ip = get_ip_address()
    url = f"http://{ip}:{PORT}"
    print("Web page available at", url)

    server = Thread(target=lambda: app.run(host="0.0.0.0", port=PORT, use_reloader=False))
    server.daemon = True
    server.start()

    # Give the server a moment to start before capturing
    time.sleep(5)
    capture_and_send(url)

    server.join()

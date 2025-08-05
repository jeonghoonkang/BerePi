import asyncio
import os
import subprocess
import time
import shutil
import urllib.request
from flask import Flask, render_template_string  # Flask와 render_template_string 임포트
from threading import Thread

app = Flask(__name__)


PORT = 5001

INFLUX_HOST = "localhost"
INFLUX_PORT = 8086
INFLUX_USER = os.environ.get("INFLUX_USER", "admin")
INFLUX_PASS = os.environ.get("INFLUX_PASS", "admin")
INFLUX_DB = "sht20"
INFLUX_MEASUREMENT = "temperature"


def find_chrome():
    """Return the path to a working Chrome/Chromium executable, if any."""
    candidates = [
        "chromium-browser",
        "chromium",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
    ]
    for name in candidates:
        path = shutil.which(name)
        if not path:
            continue
        try:
            subprocess.run([path, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return path
        except Exception:
            continue
    return None


def query_last_48h():
    """Fetch temperature readings for the last 48 hours."""
    query = f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" WHERE time > now() - 48h'
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


@app.route("/")
def index():
    data = query_last_48h()
    return render_template_string(
        """
        <html>
        <head>
            <title>SHT20 48-hour chart</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: sans-serif; margin: 20px; }
                #chart { max-width: 800px; height: 400px; border: 1px solid #eee; }
            </style>
        </head>
        <body>
            <h1>Last 48 hours</h1>
            <canvas id="chart" width="800" height="400"></canvas>
            <script>
            document.addEventListener('DOMContentLoaded', () => {
                const data = {{ data|tojson }};
                const ctx = document.getElementById('chart').getContext('2d');
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.map(p => new Date(p.time).toLocaleString()),
                        datasets: [{
                            label: 'Temperature',
                            data: data.map(p => p.value),
                            borderColor: 'blue',
                            fill: false,
                            tension: 0.1
                        }]
                    },
                    options: {
                        animation: false,
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { ticks: { maxTicksLimit: 8 } },
                            y: { title: { display: true, text: 'Temperature' } }
                        }
                    }
                });
                window.CHARTS_READY = true;
                window.status = 'ready';
            });
            </script>
        </body>
        </html>
        """,
        data=data,
    )


async def _capture_with_pyppeteer(url, outfile, chrome_path):
    from pyppeteer import launch

    browser = await launch(
        executablePath=chrome_path,
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-zygote",
        ],
    )
    try:
        page = await browser.newPage()
        await page.goto(url, waitUntil="networkidle2")
        await page.waitForFunction("window.CHARTS_READY === true")
        await page.screenshot({"path": outfile, "fullPage": True})
    finally:
        await browser.close()


def capture_and_send(url, outfile="dashboard.jpg"):
    """Capture the dashboard and send it via telegram-send."""
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_capture_with_pyppeteer(url, outfile, chrome))
    subprocess.run(["telegram-send", "-f", outfile], check=False)


if __name__ == "__main__":
    server = Thread(target=lambda: app.run(host="0.0.0.0", port=PORT, use_reloader=False))
    server.daemon = True
    server.start()


    atexit.register(influx_proc.terminate)

    # Wait for server to become reachable
    for _ in range(30):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(1)

    while True:
        try:
            capture_and_send(url)
        except Exception as exc:  # pragma: no cover
            print("Capture/send failed:", exc)
        time.sleep(12 * 3600)



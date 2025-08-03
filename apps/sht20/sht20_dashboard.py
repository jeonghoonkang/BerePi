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
            <style>
                body { font-family: sans-serif; margin: 20px; }
                canvas { max-width: 800px; margin-bottom: 30px; border: 1px solid #eee; }
                h1, h2 { color: #333; }
            </style>
        </head>
        <body>
            <h1>Monthly temperature overview</h1>
            {% for w in range(4) %}
            <h2>Week {{ loop.index }}</h2>
            <canvas id="chart{{loop.index}}" width="800" height="400"></canvas> {# Increased dimensions for better clarity in capture #}
            {% endfor %}
            <script>
            // Ensure the entire DOM is loaded before trying to access elements
            document.addEventListener('DOMContentLoaded', () => {
                const weeks = {{ weeks|tojson }};
                let chartsRenderedCount = 0;
                const totalCharts = weeks.length;
                // Flag used by the screenshot routine to detect chart completion
                window.CHARTS_READY = false;

                weeks.forEach((wk, idx) => {
                    const ctx = document.getElementById('chart'+(idx+1)).getContext('2d');
                    new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: wk.map(p => new Date(p.time).toLocaleString()), // Format time for better readability
                            datasets: [{
                                label: 'Temperature',
                                data: wk.map(p => p.value),
                                borderColor: 'blue',
                                backgroundColor: 'rgba(0, 0, 255, 0.1)', // Optional: shaded area below line
                                fill: false, // Changed from true to false for a cleaner look if desired
                                tension: 0.1 // Smooths the line
                            }]
                        },
                        options: {
                            responsive: false,
                            maintainAspectRatio: false,
                            scales: {
                                x: {
                                    ticks: {
                                        maxTicksLimit: 8, // Adjust tick limit
                                        autoSkip: true,
                                        maxRotation: 45,
                                        minRotation: 0
                                    },
                                    title: {
                                        display: true,
                                        text: 'Time'
                                    }
                                },
                                y: {
                                    title: {
                                        display: true,
                                        text: 'Temperature Value'
                                    }
                                }
                            },
                            animation: {
                                duration: 0 // Disable animation for instant rendering before capture
                            },
                            plugins: {
                                legend: {
                                    display: true
                                }
                            }
                        }
                    });
                    chartsRenderedCount++;
                    // After all charts are rendered, set the global flag
                    if (chartsRenderedCount === totalCharts) {
                        window.CHARTS_READY = true;
                    }
                });
            });
            </script>
        </body>
        </html>
        """,
        weeks=weeks,
    )




async def _capture_with_pyppeteer(url, outfile):
    """Use headless Chrome to capture a screenshot of the dashboard."""
    from pyppeteer import launch

    browser = await launch(args=["--no-sandbox"])
    page = await browser.newPage()
    await page.setViewport({"width": 1024, "height": 768})
    # Wait for all network activity (including Chart.js) to finish
    await page.goto(url, {"waitUntil": "networkidle0"})
    try:
        # Wait until the page JS reports that charts are rendered
        await page.waitForFunction("window.CHARTS_READY === true", timeout=10000)
    except Exception:
        # Fall back to a short delay if the flag wasn't set in time
        await page.waitForTimeout(2000)
    await page.screenshot({"path": outfile, "fullPage": True})
    await browser.close()


def capture_and_send(url, outfile="dashboard.jpg"):
    """Capture the given URL to an image and send via telegram-send."""
    try:
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            _capture_with_pyppeteer(url, outfile)
        )
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


# Author : Philman Jeong (ipmstyle@gmail.com)
#          Jeonghoon Kang (github.com/jeonghoonkang)

"""SHT20 sensor reader with web and storage support.

This script periodically reads temperature data from the SHT20 sensor and
exposes it through a simple web page.  Every 30 seconds the following actions
are performed:

* Read the current temperature from the sensor.
* Update an HTML page served via Flask showing the temperature and the
  host's network address.
* Store the reading in a time-series database (InfluxDB).
* Append the reading to a JSON file for local history keeping.

The original reading and conversion functions are retained so existing sensor
logic continues to work on systems with the required hardware.
"""

import json
import os
import socket
import threading
import time
import subprocess
import shutil
import atexit

import lgpio
from flask import Flask, render_template_string
from influxdb import InfluxDBClient
from datetime import datetime
from rich.console import Console

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Seoul")
except Exception:  # pragma: no cover - fallback if zoneinfo is unavailable
    from datetime import timezone, timedelta
    TZ = timezone(timedelta(hours=9))

# Constants for the SHT20 sensor
SHT20_ADDR = 0x40       # SHT20 register address
SHT20_CMD_R_T = 0xF3    # no hold Master Mode (Temperature)
SHT20_CMD_R_RH = 0xF5   # no hold Master Mode (Humidity)
SHT20_CMD_RESET = 0xFE  # soft reset

# Open the I2C bus for the sensor
bus = lgpio.i2c_open(1, SHT20_ADDR)

# Flask application setup
app = Flask(__name__)

console = Console()


# HTML template for the web page
INDEX_TEMPLATE = """
<html>
    <head>
        <title>SHT20 Sensor</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <h1>SHT20 Temperature</h1>
        <p>Temperature: {{ temp }} &deg;C</p>
        <p>IP Address: {{ ip }}</p>
        <p>Last Update: {{ ts }}</p>
        <h2>InfluxDB Info</h2>
        <p>User: {{ influx_user }}</p>
        <p>Password: {{ influx_pass }}</p>
        <p>Database: {{ influx_db }}</p>
        <p>Measurement: {{ influx_measurement }}</p>
        <h3>Query for Last Month</h3>
        <pre>{{ query }}</pre>
        <h2>Recent Temperature (last 48h)</h2>
        <canvas id="tempChart" width="400" height="200"></canvas>
        <script>
            const recent = {{ recent|tojson }};
            const ctx = document.getElementById('tempChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: recent.map(p => p.time),
                    datasets: [{
                        label: 'Temperature',
                        data: recent.map(p => p.temperature),
                        borderColor: 'red',
                        fill: false
                    }]
                },
                options: { scales: { x: { ticks: { maxTicksLimit: 6 } } } }
            });
            window.CHARTS_READY = true;
            window.status = 'ready';
        </script>
    </body>
</html>
"""

# In-memory cache of the latest reading
latest_data = {
    "temperature": None,
    "ip": None,
    "timestamp": None,
}

# JSON file used to persist readings locally
JSON_FILE = os.path.join(os.path.dirname(__file__), "sht20_data.json")

# InfluxDB connection information
INFLUX_HOST = "localhost"
INFLUX_PORT = 8086
INFLUX_USER = os.environ.get("INFLUX_USER", "admin")
INFLUX_PASS = os.environ.get("INFLUX_PASS", "admin")
INFLUX_DB = "sht20"
INFLUX_MEASUREMENT = "temperature"

# Query to fetch one month of temperature readings
QUERY_LAST_MONTH = (
    f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" WHERE time >= now() - 30d'
)

# Interval between Telegram notifications (3 hours)
SEND_INTERVAL = 3 * 60 * 60


def reading(v):
    if v == 1:
        lgpio.i2c_write_byte(bus, SHT20_CMD_R_T)
    elif v == 2:
        lgpio.i2c_write_byte(bus, SHT20_CMD_R_RH)
    else:
        return False
        
    time.sleep(.1)
    
    b = (lgpio.i2c_read_byte(bus)<<8)
    b += lgpio.i2c_read_byte(bus)
    return b

def calc(temp, humi):
    tmp_temp = -46.85 + 175.72 * float(temp) / pow(2,16)
    tmp_humi = -6 + 125 * float(humi) / pow(2,16)

    return tmp_temp, tmp_humi


def get_ip_address():
    """Return the host's primary IP address."""
    ip = "unknown"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # The address used here does not need to be reachable; it's only used
        # to determine the outgoing interface.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    return ip


def write_json(temp, ip, timestamp):
    """Append a reading to the local JSON file."""
    entry = {"time": timestamp, "temperature": temp, "ip": ip}
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
        data.append(entry)
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as exc:  # pragma: no cover - best effort logging
        print("JSON write error:", exc)


def write_influx(temp, timestamp):
    """Store a reading in InfluxDB."""
    try:
        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASS,
        )
        client.create_database(INFLUX_DB)
        client.switch_database(INFLUX_DB)
        datapoint = [{
            "measurement": INFLUX_MEASUREMENT,

            "time": timestamp,
            "fields": {"value": float(temp)},
        }]
        client.write_points(datapoint)
    except Exception as exc:  # pragma: no cover - best effort logging
        print("InfluxDB write error:", exc)


def query_recent_temperatures(hours=48):
    """Retrieve temperature points from the last ``hours`` hours."""
    try:
        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASS,
            database=INFLUX_DB,
        )
        query = (
            f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" '
            f'WHERE time >= now() - {hours}h ORDER BY time ASC'
        )
        result = client.query(query)
        points = list(result.get_points())
        return [
            {
                "time": datetime.fromisoformat(p["time"].replace("Z", "+00:00"))
                .astimezone(TZ)
                .strftime("%m-%d %H:%M"),
                "temperature": p["value"],
            }
            for p in points
        ]
    except Exception as exc:  # pragma: no cover - best effort logging
        print("InfluxDB query error:", exc)
        return []


def start_influxdb():
    """Start an InfluxDB server if one is not already running."""
    if shutil.which("influxd") is None:
        print("InfluxDB executable not found; please install InfluxDB.")
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect(("localhost", 8086))
        # Already running
        return None
    except OSError:
        pass
    finally:
        sock.close()

    try:
        proc = subprocess.Popen(
            ["influxd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return proc
    except Exception as exc:  # pragma: no cover - best effort logging
        print("Failed to start InfluxDB:", exc)
        return None


def send_plaintext(temp, ip, timestamp):
    """Send a plain text summary via telegram-send."""
    message = (
        f"Temperature: {temp:.2f} \u00b0C\n"
        f"IP Address: {ip}\n"
        f"Timestamp: {timestamp}\n"
        "\uc704\uce58: A\ub3d9 \uc11c\ubc84\uc2e4 \n"  # 위치: A동 서버실
        f"influxdb user, pass, DB, measurements {INFLUX_USER} {INFLUX_PASS} {INFLUX_DB} {INFLUX_MEASUREMENT} \n"
        f"{QUERY_LAST_MONTH}"
    )
  
    try:
        subprocess.run(["telegram-send", message], check=False)
    except Exception as exc:  # pragma: no cover - best effort logging
        print("Telegram send error:", exc)


def capture_and_send(outfile="sht20.png"):
    """Generate a temperature chart from InfluxDB data and send it."""

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASS,
            database=INFLUX_DB,
        )
        query = (
            f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" '
            f'WHERE time >= now() - 48h ORDER BY time ASC'
        )
        result = client.query(query)
        points = list(result.get_points())
        if not points:
            return

        times = [
            datetime.fromisoformat(p["time"].replace("Z", "+00:00"))
            .astimezone(TZ)
            for p in points
        ]
        temps = [p["value"] for p in points]

        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.lineplot(x=times, y=temps, ax=ax, color="red")
        ax.set_title("Recent Temperature (last 48h)")
        ax.set_xlabel("Time")
        ax.set_ylabel("Temperature (°C)")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(outfile)
        plt.close(fig)

        outfile_path = os.path.abspath(outfile)
        console.print(outfile_path)

        subprocess.run(["telegram-send", "-i", outfile_path], check=False)

    except Exception as exc:  # pragma: no cover - best effort logging
        print("Capture/send failed:", exc)


def update_loop():
    """Background thread that updates sensor data every 30 seconds."""
    last_send = 0
    while True:
        temp_raw = reading(1)
        humi_raw = reading(2)
        if not temp_raw or not humi_raw:
            print("register error")
            time.sleep(30)
            continue

        temp_c, _ = calc(temp_raw, humi_raw)
        ip = get_ip_address()
        timestamp = datetime.now(TZ).isoformat()

        latest_data["temperature"] = temp_c
        latest_data["ip"] = ip
        latest_data["timestamp"] = timestamp

        write_influx(temp_c, timestamp)
        write_json(temp_c, ip, timestamp)

        now = time.monotonic()
        if now - last_send >= SEND_INTERVAL:
            send_plaintext(temp_c, ip, timestamp)
            capture_and_send()
            last_send = now


        time.sleep(30)


@app.route("/")
def index():
    """Render a simple HTML page with the latest reading."""
    recent = query_recent_temperatures()
    return render_template_string(
        INDEX_TEMPLATE,

        temp=latest_data["temperature"],
        ip=latest_data["ip"],
        ts=latest_data["timestamp"],
        influx_user=INFLUX_USER,
        influx_pass=INFLUX_PASS,
        influx_db=INFLUX_DB,
        influx_measurement=INFLUX_MEASUREMENT,
        query=QUERY_LAST_MONTH,
        recent=recent,
    )


if __name__ == "__main__":
    influx_process = start_influxdb()
    if influx_process is not None:
        atexit.register(influx_process.terminate)

    # Start background thread for sensor updates
    thread = threading.Thread(target=update_loop, daemon=True)
    thread.start()

    # Store the initial IP address so the web page has content immediately
    latest_data["ip"] = get_ip_address()
    server = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, use_reloader=False)
    )
    server.daemon = True
    server.start()

    server.join()

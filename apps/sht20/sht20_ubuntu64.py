
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

import lgpio
from flask import Flask, render_template_string
from influxdb import InfluxDBClient

# Constants for the SHT20 sensor
SHT20_ADDR = 0x40       # SHT20 register address
SHT20_CMD_R_T = 0xF3    # no hold Master Mode (Temperature)
SHT20_CMD_R_RH = 0xF5   # no hold Master Mode (Humidity)
SHT20_CMD_RESET = 0xFE  # soft reset

# Open the I2C bus for the sensor
bus = lgpio.i2c_open(1, SHT20_ADDR)

# Flask application setup
app = Flask(__name__)

# In-memory cache of the latest reading
latest_data = {
    "temperature": None,
    "ip": None,
    "timestamp": None,
}

# JSON file used to persist readings locally
JSON_FILE = os.path.join(os.path.dirname(__file__), "sht20_data.json")

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
        client = InfluxDBClient(host="localhost", port=8086)
        dbname = "sht20"
        client.create_database(dbname)
        client.switch_database(dbname)
        datapoint = [{
            "measurement": "temperature",
            "time": timestamp,
            "fields": {"value": float(temp)},
        }]
        client.write_points(datapoint)
    except Exception as exc:  # pragma: no cover - best effort logging
        print("InfluxDB write error:", exc)


def update_loop():
    """Background thread that updates sensor data every 30 seconds."""
    while True:
        temp_raw = reading(1)
        humi_raw = reading(2)
        if not temp_raw or not humi_raw:
            print("register error")
            time.sleep(30)
            continue

        temp_c, _ = calc(temp_raw, humi_raw)
        ip = get_ip_address()
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        latest_data["temperature"] = temp_c
        latest_data["ip"] = ip
        latest_data["timestamp"] = timestamp

        write_influx(temp_c, timestamp)
        write_json(temp_c, ip, timestamp)

        time.sleep(30)


@app.route("/")
def index():
    """Render a simple HTML page with the latest reading."""
    return render_template_string(
        """
        <html>
            <head><title>SHT20 Sensor</title></head>
            <body>
                <h1>SHT20 Temperature</h1>
                <p>Temperature: {{ temp }} &deg;C</p>
                <p>IP Address: {{ ip }}</p>
                <p>Last Update: {{ ts }}</p>
            </body>
        </html>
        """,
        temp=latest_data["temperature"],
        ip=latest_data["ip"],
        ts=latest_data["timestamp"],
    )


if __name__ == "__main__":
    # Start background thread for sensor updates
    thread = threading.Thread(target=update_loop, daemon=True)
    thread.start()

    # Store the initial IP address so the web page has content immediately
    latest_data["ip"] = get_ip_address()

    # Run the web server
    app.run(host="0.0.0.0", port=5000)



#!/usr/bin/env python3
import datetime
import os
import subprocess
from pathlib import Path

import requests
from influxdb import InfluxDBClient

INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))
INFLUX_USER = os.getenv("INFLUX_USER", "admin")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "admin")
INFLUX_DB = os.getenv("INFLUX_DB", "sht20")
INFLUX_MEASUREMENT = os.getenv("INFLUX_MEASUREMENT", "temperature")
INFLUX_FIELD = os.getenv("INFLUX_FIELD", "value")


def fetch_recent_values(client, limit=10):
    result = client.query(
        f'SELECT "value" FROM "{INFLUX_MEASUREMENT}" ORDER BY time DESC LIMIT {limit}'
    )
    return list(result.get_points(measurement=INFLUX_MEASUREMENT))


def render_week(host, port, db, user, password, measurement, field, start, stop, path):
    query = (
        f"SELECT mean(\"{field}\") FROM \"{measurement}\" "
        f"WHERE time >= '{start.isoformat()}Z' AND time <= '{stop.isoformat()}Z'"
    )
    params = {
        "db": db,
        "u": user,
        "p": password,
        "q": query,
        "epoch": "ms",
        "format": "png",
        "width": 1000,
        "height": 400,
    }
    url = f"http://{host}:{port}/render"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    with open(path, "wb") as file:
        file.write(resp.content)


def send_image(path):
    subprocess.run(["telegram-send", "--image", str(path)], check=False)


def main():
    try:
        client = InfluxDBClient(
            host=INFLUX_HOST,
            port=INFLUX_PORT,
            username=INFLUX_USER,
            password=INFLUX_PASSWORD,
            database=INFLUX_DB,
        )
        client.ping()
        latest = fetch_recent_values(client, limit=5)
        print(latest)


        now = datetime.datetime.utcnow()
        for i in range(4):
            end = now - datetime.timedelta(weeks=i)
            start = now - datetime.timedelta(weeks=i + 1)
            img_path = Path(f"week_{i + 1}.png")
            render_week(
                INFLUX_HOST,
                INFLUX_PORT,
                INFLUX_DB,
                INFLUX_USER,
                INFLUX_PASSWORD,
                INFLUX_MEASUREMENT,

                INFLUX_FIELD,
                start,
                end,
                img_path,
            )
            send_image(img_path)
    except Exception as exc:
        print(f"Failed to connect to InfluxDB: {exc}")



if __name__ == "__main__":
    main()


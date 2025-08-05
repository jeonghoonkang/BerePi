#!/usr/bin/env python3
import datetime
import os
import subprocess
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

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


def render_week(client, measurement, field, start, stop, path):
    query = (
        f"SELECT \"{field}\" FROM \"{measurement}\" "
        f"WHERE time >= '{start.isoformat()}Z' AND time <= '{stop.isoformat()}Z'"
    )
    result = client.query(query)
    points = list(result.get_points(measurement=measurement))
    if not points:
        print("No data found for the specified range")
        return

    df = pd.DataFrame(points)
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)

    ax = df[field].plot(figsize=(10, 4), title=f"{measurement} {start.date()} - {stop.date()}")
    ax.set_ylabel(field)
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)



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
                client,
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


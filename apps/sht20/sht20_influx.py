#!/usr/bin/env python3
import datetime
import os
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from influxdb_client import InfluxDBClient

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "")
MEASUREMENT = os.getenv("INFLUX_MEASUREMENT", "sht20")

def fetch_week(client, start, stop):
    query = f"""
    from(bucket: \"{INFLUX_BUCKET}\")
      |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
      |> filter(fn: (r) => r[\"_measurement\"] == \"{MEASUREMENT}\")
    """
    df = client.query_api().query_data_frame(org=INFLUX_ORG, query=query)
    if isinstance(df, list):
        df = pd.concat(df, ignore_index=True)
    return df

def plot_week(df, title, path):
    plt.figure(figsize=(10, 4))
    plt.plot(df["_time"], df["_value"])
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

def send_image(path):
    subprocess.run(["telegram-send", "--image", str(path)], check=False)

def main():
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            # Ensure the server is reachable before proceeding.
            client.ping()

            now = datetime.datetime.utcnow()
            for i in range(4):
                end = now - datetime.timedelta(weeks=i)
                start = now - datetime.timedelta(weeks=i + 1)
                df = fetch_week(client, start, end)
                if df.empty:
                    continue
                df["_time"] = pd.to_datetime(df["_time"])
                img_path = Path(f"week_{i + 1}.png")
                title = f"Week {i + 1}: {start.date()} to {end.date()}"
                plot_week(df, title, img_path)
                send_image(img_path)
    except Exception as exc:
        print(f"Failed to connect to InfluxDB: {exc}")

if __name__ == "__main__":
    main()

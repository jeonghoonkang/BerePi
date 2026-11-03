#!/usr/bin/env python3
import datetime
import logging
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from influxdb import InfluxDBClient
from rich.console import Console

INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))
INFLUX_USER = os.getenv("INFLUX_USER", "")
INFLUX_PASSWORD = os.getenv("INFLUX_PASSWORD", "")
INFLUX_DB = os.getenv("INFLUX_DB", "")
INFLUX_MEASUREMENT = os.getenv("INFLUX_MEASUREMENT", "temperature")
INFLUX_FIELD = os.getenv("INFLUX_FIELD", "value")

console = Console()
sns.set_theme()
logger = logging.getLogger(__name__)



def fetch_recent_values(client, limit=10):
    result = client.query(
        f'SELECT "{INFLUX_FIELD}" FROM "{INFLUX_MEASUREMENT}" ORDER BY time DESC LIMIT {limit}'
    )
    return list(result.get_points(measurement=INFLUX_MEASUREMENT))


def render_week(client, measurement, field, start, stop, path):
    start_utc = start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stop_utc = stop.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = (
        f"SELECT \"{field}\" FROM \"{measurement}\" "
        f"WHERE time >= '{start_utc}' AND time <= '{stop_utc}'"

    )
    logger.info("조회 기간 KST: %s ~ %s; UTC: %s ~ %s; 이미지: %s",
                start.isoformat(), stop.isoformat(), start_utc, stop_utc, path)
    result = client.query(query)
    points = list(result.get_points(measurement=measurement))
    logger.info("조회 결과: %d건", len(points))
    if not points:
        logger.warning("조회 기간에 데이터 없음. 이미지 생성 및 전송 생략")
        return False

    df = pd.DataFrame(points)
    df["time"] = pd.to_datetime(df["time"]).dt.tz_convert("Asia/Seoul")

    fig, ax = plt.subplots(figsize=(10, 4))
    sns.lineplot(data=df, x="time", y=field, ax=ax)
    ax.set_title(
        f"{measurement} {start.date()} - {stop.date()} \U0001F321\uFE0F"
    )
    ax.set_ylabel("Temperature (°C)")
    fig.tight_layout()
    fig.savefig(path)
    console.print(f"Chart saved: {path}")
    plt.close(fig)
    return True


def send_image(path, caption=""):
    console.print(f"Sending image: {path}")
    subprocess.run(["telegram-send", "--image", str(path), "--caption", caption], check=True)


def latest_data_text(points):
    if not points:
        return "가장 최근 데이터: 없음 (설정한 measurement/field에 저장된 데이터 없음)"
    timestamp = datetime.datetime.fromisoformat(points[0]["time"].replace("Z", "+00:00"))
    return f"가장 최근 데이터: {timestamp.astimezone(ZoneInfo('Asia/Seoul')):%Y-%m-%d %H:%M:%S KST} (UTC: {points[0]['time']})"


def send_no_data(start, stop, latest_text):
    message = (
        "조회 기간에 최근 데이터가 없어 이미지 전송을 건너뜁니다.\n"
        f"조회 기간 (KST): {start:%Y-%m-%d %H:%M:%S} ~ {stop:%Y-%m-%d %H:%M:%S}\n"
        f"{latest_text}"
    )
    subprocess.run(["telegram-send", "--", message], check=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("DB 설정: host=%s port=%s database=%s user=%s measurement=%s field=%s",
                INFLUX_HOST, INFLUX_PORT, INFLUX_DB or '(미설정)',
                INFLUX_USER or '(미설정)', INFLUX_MEASUREMENT, INFLUX_FIELD)
    client = None
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
        latest_text = latest_data_text(latest)
        logger.info("%s", latest_text)

        tz = ZoneInfo("Asia/Seoul")
        now = datetime.datetime.now(tz)
        for i in range(4):
            end = now - datetime.timedelta(weeks=i)
            start = now - datetime.timedelta(weeks=i + 1)
            img_path = Path(f"week_{i + 1}.png").resolve()
            generated = render_week(
                client,
                INFLUX_MEASUREMENT,

                INFLUX_FIELD,
                start,
                end,
                img_path,
            )
            try:
                if generated:
                    send_image(img_path, latest_text)
                else:
                    send_no_data(start, end, latest_text)
            except (OSError, subprocess.CalledProcessError) as exc:
                logger.error("Telegram 전송 실패: %s", type(exc).__name__)
    except Exception as exc:
        logger.error("DB 조회 또는 그래프 처리 실패: %s", type(exc).__name__)
    finally:
        if client is not None:
            client.close()



if __name__ == "__main__":
    main()


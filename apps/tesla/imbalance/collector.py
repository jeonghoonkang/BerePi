#!/usr/bin/env python3
"""Tesla battery imbalance collector.

Collects charge-state data from Tesla Owner/Fleet API and stores extracted
battery imbalance related metrics into SQLite.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

API_TIMEOUT_SECONDS = float(os.getenv("TESLA_API_TIMEOUT_SECONDS", "20"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
DB_PATH = os.getenv("DB_PATH", "./data/imbalance.db")
API_BASE_URL = os.getenv("TESLA_API_BASE_URL", "https://fleet-api.prd.na.vn.cloud.tesla.com")
TESLA_ACCESS_TOKEN = os.getenv("TESLA_ACCESS_TOKEN", "")
TESLA_VEHICLE_ID = os.getenv("TESLA_VEHICLE_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Keys that may contain imbalance-like values depending on API version/vehicle.
IMBALANCE_CANDIDATE_PATHS: list[tuple[str, ...]] = [
    ("response", "charge_state", "battery_imbalance"),
    ("response", "charge_state", "cell_imbalance"),
    ("response", "charge_state", "battery_cell_imbalance"),
    ("response", "drive_state", "battery_imbalance"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def require_config() -> None:
    missing = []
    if not TESLA_ACCESS_TOKEN:
        missing.append("TESLA_ACCESS_TOKEN")
    if not TESLA_VEHICLE_ID:
        missing.append("TESLA_VEHICLE_ID")
    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")


def get_nested(payload: dict[str, Any], path: Iterable[str]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def ensure_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS battery_imbalance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at_utc TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                battery_level REAL,
                usable_battery_level REAL,
                soc_gap REAL,
                imbalance_value REAL,
                imbalance_source_key TEXT,
                charge_state_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_battery_imbalance_collected_at
            ON battery_imbalance(collected_at_utc)
            """
        )
        conn.commit()


def fetch_vehicle_charge_state(session: requests.Session) -> dict[str, Any]:
    url = f"{API_BASE_URL.rstrip('/')}/api/1/vehicles/{TESLA_VEHICLE_ID}/vehicle_data?endpoints=charge_state"
    headers = {
        "Authorization": f"Bearer {TESLA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    response = session.get(url, headers=headers, timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    if payload.get("error"):
        raise RuntimeError(f"Tesla API returned error: {payload['error']}")

    return payload


def extract_imbalance(payload: dict[str, Any]) -> tuple[float | None, str | None]:
    for path in IMBALANCE_CANDIDATE_PATHS:
        value = get_nested(payload, path)
        if isinstance(value, (int, float)):
            return float(value), ".".join(path)
    return None, None


def collect_once(session: requests.Session) -> None:
    payload = fetch_vehicle_charge_state(session)
    charge_state = get_nested(payload, ("response", "charge_state"))
    if not isinstance(charge_state, dict):
        raise RuntimeError("Tesla API response missing response.charge_state object")

    battery_level = charge_state.get("battery_level")
    usable_battery_level = charge_state.get("usable_battery_level")

    battery_level_value = float(battery_level) if isinstance(battery_level, (int, float)) else None
    usable_battery_level_value = (
        float(usable_battery_level) if isinstance(usable_battery_level, (int, float)) else None
    )
    soc_gap = None
    if battery_level_value is not None and usable_battery_level_value is not None:
        soc_gap = battery_level_value - usable_battery_level_value

    imbalance_value, imbalance_source_key = extract_imbalance(payload)

    collected_at_utc = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT INTO battery_imbalance (
                collected_at_utc,
                vehicle_id,
                battery_level,
                usable_battery_level,
                soc_gap,
                imbalance_value,
                imbalance_source_key,
                charge_state_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collected_at_utc,
                str(TESLA_VEHICLE_ID),
                battery_level_value,
                usable_battery_level_value,
                soc_gap,
                imbalance_value,
                imbalance_source_key,
                json.dumps(charge_state, ensure_ascii=False),
            ),
        )
        conn.commit()

    logging.info(
        "Saved sample vehicle_id=%s battery_level=%s usable_battery_level=%s soc_gap=%s imbalance=%s",
        TESLA_VEHICLE_ID,
        battery_level_value,
        usable_battery_level_value,
        soc_gap,
        imbalance_value,
    )


def run() -> None:
    setup_logging()
    require_config()
    ensure_db()

    logging.info("Starting Tesla battery imbalance collector (interval=%ss)", POLL_INTERVAL_SECONDS)
    with requests.Session() as session:
        while True:
            try:
                collect_once(session)
            except requests.HTTPError as exc:
                logging.error("HTTP error while calling Tesla API: %s", exc)
            except requests.RequestException as exc:
                logging.error("Network error while calling Tesla API: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Unexpected collection error: %s", exc)

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()

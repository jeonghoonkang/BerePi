from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


DATABASE_PATH = Path(os.environ.get("FLEET_DB_PATH", "/data/fleet.sqlite3"))
HMAC_SECRET = os.environ.get("FLEET_HMAC_SECRET", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

if len(HMAC_SECRET) < 32:
    raise RuntimeError("FLEET_HMAC_SECRET must contain at least 32 characters")
if len(ADMIN_TOKEN) < 24:
    raise RuntimeError("ADMIN_TOKEN must contain at least 24 characters")


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra="allow")
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    observed_at: str
    hostname: str = Field(max_length=255)


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    observed_at: str
    event: str = Field(min_length=1, max_length=128)


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                observed_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        database.execute(
            "CREATE INDEX IF NOT EXISTS ix_heartbeats_device_id_id "
            "ON heartbeats(device_id, id DESC)"
        )
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                observed_at TEXT NOT NULL,
                event TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        database.execute(
            "CREATE INDEX IF NOT EXISTS ix_events_device_id_id "
            "ON events(device_id, id DESC)"
        )


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    database = sqlite3.connect(DATABASE_PATH, timeout=10)
    database.row_factory = sqlite3.Row
    try:
        yield database
        database.commit()
    finally:
        database.close()


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def expected_device_token(device_id: str) -> str:
    digest = hmac.new(HMAC_SECRET.encode(), device_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def verify_device(device_id: str, authorization: str | None) -> None:
    supplied = bearer_token(authorization)
    if not hmac.compare_digest(supplied, expected_device_token(device_id)):
        raise HTTPException(status_code=403, detail="invalid device token")


def verify_admin(authorization: str | None = Header(default=None)) -> None:
    supplied = bearer_token(authorization)
    if not hmac.compare_digest(supplied, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="invalid admin token")


initialize_database()
app = FastAPI(title="Sononet Fleet API", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/heartbeat", status_code=202)
def heartbeat(body: Heartbeat, authorization: str | None = Header(default=None)) -> dict[str, str]:
    verify_device(body.device_id, authorization)
    payload = body.model_dump_json()
    with connect() as database:
        database.execute(
            "INSERT INTO heartbeats(device_id, observed_at, payload) VALUES (?, ?, ?)",
            (body.device_id, body.observed_at, payload),
        )
    return {"status": "accepted"}


@app.post("/v1/events", status_code=202)
def event(body: Event, authorization: str | None = Header(default=None)) -> dict[str, str]:
    verify_device(body.device_id, authorization)
    payload = body.model_dump_json()
    with connect() as database:
        database.execute(
            "INSERT INTO events(device_id, observed_at, event, payload) VALUES (?, ?, ?, ?)",
            (body.device_id, body.observed_at, body.event, payload),
        )
    return {"status": "accepted"}


@app.get("/v1/devices", dependencies=[Depends(verify_admin)])
def devices() -> list[dict[str, Any]]:
    with connect() as database:
        rows = database.execute(
            """
            SELECT h.device_id, h.received_at, h.observed_at, h.payload
            FROM heartbeats h
            INNER JOIN (
                SELECT device_id, MAX(id) AS max_id FROM heartbeats GROUP BY device_id
            ) latest ON latest.max_id = h.id
            ORDER BY h.device_id
            """
        ).fetchall()
    return [
        {
            "device_id": row["device_id"],
            "received_at": row["received_at"],
            "observed_at": row["observed_at"],
            "heartbeat": json.loads(row["payload"]),
        }
        for row in rows
    ]


@app.get("/v1/devices/{device_id}/heartbeats", dependencies=[Depends(verify_admin)])
def device_heartbeats(
    device_id: str, limit: int = Query(default=100, ge=1, le=1000)
) -> list[dict[str, Any]]:
    with connect() as database:
        rows = database.execute(
            """
            SELECT received_at, observed_at, payload FROM heartbeats
            WHERE device_id=? ORDER BY id DESC LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
    return [
        {
            "received_at": row["received_at"],
            "observed_at": row["observed_at"],
            "heartbeat": json.loads(row["payload"]),
        }
        for row in rows
    ]


@app.get("/v1/devices/{device_id}/events", dependencies=[Depends(verify_admin)])
def device_events(
    device_id: str, limit: int = Query(default=100, ge=1, le=1000)
) -> list[dict[str, Any]]:
    with connect() as database:
        rows = database.execute(
            """
            SELECT received_at, observed_at, event, payload FROM events
            WHERE device_id=? ORDER BY id DESC LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
    return [
        {
            "received_at": row["received_at"],
            "observed_at": row["observed_at"],
            "event": row["event"],
            "payload": json.loads(row["payload"]),
        }
        for row in rows
    ]

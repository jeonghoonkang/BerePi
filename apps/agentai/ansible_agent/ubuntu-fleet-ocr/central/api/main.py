from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


DATABASE_PATH = Path(os.environ.get("FLEET_DB_PATH", "/data/fleet.sqlite3"))
HMAC_SECRET = os.environ.get("FLEET_HMAC_SECRET", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
ENROLLMENT_TOKEN = os.environ.get("FLEET_ENROLLMENT_TOKEN", "")
CONFLICT_WINDOW_SECONDS = int(os.environ.get("FLEET_ID_CONFLICT_WINDOW_SECONDS", "86400"))
if CONFLICT_WINDOW_SECONDS < 60:
    raise RuntimeError("FLEET_ID_CONFLICT_WINDOW_SECONDS must be at least 60")
logger = logging.getLogger("fleet.identity")

if len(HMAC_SECRET) < 32:
    raise RuntimeError("FLEET_HMAC_SECRET must contain at least 32 characters")
if len(ADMIN_TOKEN) < 24:
    raise RuntimeError("ADMIN_TOKEN must contain at least 24 characters")
if ENROLLMENT_TOKEN and (len(ENROLLMENT_TOKEN) < 32 or ENROLLMENT_TOKEN.startswith("CHANGE_ME")):
    raise RuntimeError("FLEET_ENROLLMENT_TOKEN must contain at least 32 random characters")


class Registration(BaseModel):
    # A random per-installation secret, persisted on the client BEFORE the request.
    # Its hash is the idempotency key; neither MAC addresses nor hostnames identify devices.
    registration_key: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class RegisteredDevice(BaseModel):
    device_id: str
    device_token: str


class ManualIdentity(BaseModel):
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra="allow")
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    observed_at: str
    hostname: str = Field(max_length=255)
    instance_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")
    device_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    observed_at: str
    event: str = Field(min_length=1, max_length=128)


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE_PATH, timeout=10)) as database, database:
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
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id TEXT PRIMARY KEY,
                registration_hash TEXT UNIQUE,
                registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Preserve IDs already reported by older manually configured clients.
        database.execute(
            "INSERT OR IGNORE INTO device_registry(device_id) "
            "SELECT device_id FROM heartbeats UNION SELECT device_id FROM events"
        )
        database.execute(
            "CREATE TABLE IF NOT EXISTS device_sequence ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton = 1), "
            "next_number INTEGER NOT NULL CHECK(next_number > 0))"
        )
        database.execute("INSERT OR IGNORE INTO device_sequence VALUES (1, 1)")
        database.execute(
            "CREATE TABLE IF NOT EXISTS device_instances ("
            "instance_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, "
            "hostname TEXT NOT NULL, last_seen INTEGER NOT NULL)"
        )
        database.execute(
            "CREATE INDEX IF NOT EXISTS ix_device_instances_device_seen "
            "ON device_instances(device_id, last_seen)"
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


def verify_enrollment(authorization: str | None = Header(default=None)) -> None:
    if not ENROLLMENT_TOKEN:
        raise HTTPException(status_code=503, detail="device enrollment is disabled")
    if not hmac.compare_digest(bearer_token(authorization), ENROLLMENT_TOKEN):
        raise HTTPException(status_code=403, detail="invalid enrollment token")


initialize_database()
app = FastAPI(title="Sononet Fleet API", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/devices/register", dependencies=[Depends(verify_enrollment)])
def register_device(body: Registration) -> RegisteredDevice:
    registration_hash = hashlib.sha256(body.registration_key.encode()).hexdigest()
    with connect() as database:
        # Serialize lookup + allocation + insertion across threads/processes.
        # UNIQUE constraints remain the final guard against duplicate allocations.
        database.execute("BEGIN IMMEDIATE")
        row = database.execute(
            "SELECT device_id FROM device_registry WHERE registration_hash=?",
            (registration_hash,),
        ).fetchone()
        if row is not None:
            device_id = row["device_id"]
        else:
            number = database.execute(
                "SELECT next_number FROM device_sequence WHERE singleton=1"
            ).fetchone()[0]
            while True:
                device_id = f"SN-{number:06d}"
                number += 1
                if database.execute(
                    "SELECT 1 FROM device_registry WHERE device_id=?", (device_id,)
                ).fetchone() is None:
                    break
            database.execute(
                "INSERT INTO device_registry(device_id, registration_hash) VALUES (?, ?)",
                (device_id, registration_hash),
            )
            database.execute(
                "UPDATE device_sequence SET next_number=? WHERE singleton=1", (number,)
            )
    # The transaction commits before a success response is returned. Retrying a lost
    # response returns the same ID and token without consuming another number.
    return RegisteredDevice(device_id=device_id, device_token=expected_device_token(device_id))


@app.post("/v1/devices/manual", dependencies=[Depends(verify_enrollment)])
def manual_identity(body: ManualIdentity) -> RegisteredDevice:
    # Deliberately allow an already-used ID. This endpoint authenticates the chosen
    # ID but never allocates a number; heartbeats identify conflicting installations.
    with connect() as database:
        database.execute("INSERT OR IGNORE INTO device_registry(device_id) VALUES (?)",
                         (body.device_id,))
    return RegisteredDevice(device_id=body.device_id,
                            device_token=expected_device_token(body.device_id))


def identity_status(database: sqlite3.Connection, device_id: str, now: int) -> dict[str, Any]:
    rows = database.execute(
        "SELECT instance_id, hostname, last_seen FROM device_instances "
        "WHERE device_id=? AND last_seen>=? ORDER BY instance_id",
        (device_id, now - CONFLICT_WINDOW_SECONDS),
    ).fetchall()
    return {"status": "conflict" if len(rows) > 1 else "clear",
            "instance_count": len(rows), "instances": [dict(row) for row in rows],
            "checked_at": now, "window_seconds": CONFLICT_WINDOW_SECONDS}


@app.get("/v1/id-conflicts", dependencies=[Depends(verify_admin)])
def id_conflicts() -> list[dict[str, Any]]:
    now = int(time.time())
    with connect() as database:
        database.execute("BEGIN")
        rows = database.execute(
            "SELECT device_id FROM device_instances WHERE last_seen>=? "
            "GROUP BY device_id HAVING COUNT(*)>1 ORDER BY device_id",
            (now - CONFLICT_WINDOW_SECONDS,),
        ).fetchall()
        return [{"device_id": row["device_id"], **identity_status(database, row["device_id"], now)}
                for row in rows]


@app.get("/v1/registrations", dependencies=[Depends(verify_admin)])
def registrations() -> list[dict[str, Any]]:
    with connect() as database:
        rows = database.execute(
            "SELECT device_id, registered_at FROM device_registry ORDER BY device_id"
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/v1/heartbeat", status_code=202)
def heartbeat(body: Heartbeat, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    verify_device(body.device_id, authorization)
    payload = body.model_dump_json()
    with connect() as database:
        database.execute("BEGIN IMMEDIATE")
        database.execute(
            "INSERT OR IGNORE INTO device_registry(device_id) VALUES (?)", (body.device_id,)
        )
        database.execute(
            "INSERT INTO heartbeats(device_id, observed_at, payload) VALUES (?, ?, ?)",
            (body.device_id, body.observed_at, payload),
        )
        now = int(time.time())
        if body.instance_id is not None:
            # One instance has one current display ID. Changing it resolves the old
            # claim immediately instead of leaving a duplicate until expiry.
            database.execute(
                "INSERT INTO device_instances(instance_id, device_id, hostname, last_seen) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(instance_id) DO UPDATE SET "
                "device_id=excluded.device_id, hostname=excluded.hostname, last_seen=excluded.last_seen",
                (body.instance_id, body.device_id, body.hostname, now),
            )
        check = identity_status(database, body.device_id, now)
        if body.instance_id is None:
            check["status"] = "unverified"
    if check["status"] == "conflict":
        logger.warning("device_id_conflict device_id=%s instance_count=%s",
                       body.device_id, check["instance_count"])
    return {"status": "accepted", "id_check": check}


@app.post("/v1/events", status_code=202)
def event(body: Event, authorization: str | None = Header(default=None)) -> dict[str, str]:
    verify_device(body.device_id, authorization)
    payload = body.model_dump_json()
    with connect() as database:
        database.execute(
            "INSERT OR IGNORE INTO device_registry(device_id) VALUES (?)", (body.device_id,)
        )
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

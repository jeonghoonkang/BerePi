from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class Room:
    id: int
    name: str


@dataclass(frozen=True)
class Reservation:
    id: int
    room_id: int
    title: str
    start_iso: str
    end_iso: str
    created_at_iso: str


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                start_iso TEXT NOT NULL,
                end_iso TEXT NOT NULL,
                created_at_iso TEXT NOT NULL,
                FOREIGN KEY(room_id) REFERENCES rooms(id)
            )
            """
        )


def list_rooms(db_path: Path) -> list[Room]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT id, name FROM rooms ORDER BY id").fetchall()
    return [Room(int(r["id"]), str(r["name"])) for r in rows]


def upsert_rooms(db_path: Path, names: Iterable[str], max_rooms: int = 10) -> None:
    cleaned: list[str] = []
    for n in names:
        v = (n or "").strip()
        if not v:
            continue
        if v in cleaned:
            continue
        cleaned.append(v)
        if len(cleaned) >= max_rooms:
            break

    with _connect(db_path) as conn:
        existing = conn.execute("SELECT id, name FROM rooms ORDER BY id").fetchall()
        existing_names = {str(r["name"]) for r in existing}

        for name in cleaned:
            if name not in existing_names:
                conn.execute("INSERT INTO rooms(name) VALUES (?)", (name,))

        keep_names = set(cleaned)
        if keep_names:
            conn.execute(
                "DELETE FROM rooms WHERE name NOT IN (%s)" % ",".join("?" * len(keep_names)),
                tuple(sorted(keep_names)),
            )
        else:
            conn.execute("DELETE FROM rooms")


def list_reservations(db_path: Path, room_id: Optional[int] = None) -> list[Reservation]:
    with _connect(db_path) as conn:
        if room_id is None:
            rows = conn.execute(
                """
                SELECT id, room_id, title, start_iso, end_iso, created_at_iso
                FROM reservations
                ORDER BY start_iso
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, room_id, title, start_iso, end_iso, created_at_iso
                FROM reservations
                WHERE room_id = ?
                ORDER BY start_iso
                """,
                (room_id,),
            ).fetchall()
    return [
        Reservation(
            int(r["id"]),
            int(r["room_id"]),
            str(r["title"]),
            str(r["start_iso"]),
            str(r["end_iso"]),
            str(r["created_at_iso"]),
        )
        for r in rows
    ]


def get_reservation(db_path: Path, reservation_id: int) -> Optional[Reservation]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, room_id, title, start_iso, end_iso, created_at_iso
            FROM reservations
            WHERE id = ?
            """,
            (reservation_id,),
        ).fetchone()
    if row is None:
        return None
    return Reservation(
        int(row["id"]),
        int(row["room_id"]),
        str(row["title"]),
        str(row["start_iso"]),
        str(row["end_iso"]),
        str(row["created_at_iso"]),
    )


def create_reservation(
    db_path: Path,
    room_id: int,
    title: str,
    start_iso: str,
    end_iso: str,
) -> int:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO reservations(room_id, title, start_iso, end_iso, created_at_iso)
            VALUES (?, ?, ?, ?, ?)
            """,
            (room_id, title, start_iso, end_iso, now),
        )
        return int(cur.lastrowid)


def update_reservation(
    db_path: Path,
    reservation_id: int,
    room_id: int,
    title: str,
    start_iso: str,
    end_iso: str,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE reservations
            SET room_id = ?, title = ?, start_iso = ?, end_iso = ?
            WHERE id = ?
            """,
            (room_id, title, start_iso, end_iso, reservation_id),
        )


def delete_reservation(db_path: Path, reservation_id: int) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))


def has_conflict(
    db_path: Path,
    room_id: int,
    start_iso: str,
    end_iso: str,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    query = """
        SELECT COUNT(1) AS cnt
        FROM reservations
        WHERE room_id = ?
          AND NOT (end_iso <= ? OR start_iso >= ?)
    """
    params: list[object] = [room_id, start_iso, end_iso]
    if exclude_reservation_id is not None:
        query += " AND id != ?"
        params.append(exclude_reservation_id)
    with _connect(db_path) as conn:
        row = conn.execute(query, tuple(params)).fetchone()
    return int(row["cnt"]) > 0


"""Load CSV data from MinIO into SingleStore and compute storage periods.

This script demonstrates how to read a CSV object stored in a MinIO bucket,
insert the rows into a SingleStore (MySQL compatible) table and calculate
for each record identifier the period during which data has been stored.

The script expects the following environment variables for configuration:

MINIO_ENDPOINT      - URL to the MinIO service (e.g. "play.min.io:9000")
MINIO_ACCESS_KEY    - MinIO access key
MINIO_SECRET_KEY    - MinIO secret key
MINIO_BUCKET        - Name of the bucket containing the CSV file
MINIO_OBJECT        - Object name of the CSV file

S2_HOST             - SingleStore host address
S2_PORT             - SingleStore port (default: 3306)
S2_USER             - Username for SingleStore
S2_PASSWORD         - Password for SingleStore
S2_DATABASE         - Target database name
S2_TABLE            - Target table name
S2_ID_FIELD         - Field name representing the identifier (default: "id")
S2_TIME_FIELD       - Field name representing the timestamp (default: "timestamp")

The table is expected to already exist in the database with columns matching
those found in the CSV file.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from minio import Minio
import pymysql


@dataclass
class MinioConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    obj_name: str
    secure: bool = False


@dataclass
class DBConfig:
    host: str
    user: str
    password: str
    database: str
    table: str
    port: int = 3306
    id_field: str = "id"
    time_field: str = "timestamp"


def read_csv_from_minio(cfg: MinioConfig) -> List[dict]:
    """Return rows from the CSV object stored in MinIO."""
    client = Minio(
        cfg.endpoint,
        access_key=cfg.access_key,
        secret_key=cfg.secret_key,
        secure=cfg.secure,
    )
    response = client.get_object(cfg.bucket, cfg.obj_name)
    try:
        data = response.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(data))
        return list(reader)
    finally:
        response.close()
        response.release_conn()


def insert_rows(conn, table: str, rows: Iterable[dict]) -> None:
    """Insert iterable of dictionaries into the given table."""
    rows = list(rows)
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ",".join(["%s"] * len(columns))
    column_list = ",".join(columns)
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    values = [tuple(row[col] for col in columns) for row in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, values)
    conn.commit()


def calculate_periods(conn, cfg: DBConfig) -> List[Tuple]:
    """Return list of (id, start_time, end_time, seconds) tuples."""
    query = (
        f"SELECT {cfg.id_field}, MIN({cfg.time_field}) AS start_time, "
        f"MAX({cfg.time_field}) AS end_time, "
        f"TIMESTAMPDIFF(SECOND, MIN({cfg.time_field}), MAX({cfg.time_field})) "
        f"AS duration_seconds FROM {cfg.table} GROUP BY {cfg.id_field}"
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def load_csv_to_singlestore(minio_cfg: MinioConfig, db_cfg: DBConfig) -> List[Tuple]:
    """Load CSV data from MinIO into SingleStore and compute storage periods."""
    rows = read_csv_from_minio(minio_cfg)
    conn = pymysql.connect(
        host=db_cfg.host,
        user=db_cfg.user,
        password=db_cfg.password,
        database=db_cfg.database,
        port=db_cfg.port,
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        insert_rows(conn, db_cfg.table, rows)
        return calculate_periods(conn, db_cfg)
    finally:
        conn.close()


def main() -> None:  # pragma: no cover - convenience wrapper
    minio_cfg = MinioConfig(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        bucket=os.environ["MINIO_BUCKET"],
        obj_name=os.environ["MINIO_OBJECT"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    db_cfg = DBConfig(
        host=os.environ["S2_HOST"],
        user=os.environ["S2_USER"],
        password=os.environ["S2_PASSWORD"],
        database=os.environ["S2_DATABASE"],
        table=os.environ["S2_TABLE"],
        port=int(os.environ.get("S2_PORT", "3306")),
        id_field=os.environ.get("S2_ID_FIELD", "id"),
        time_field=os.environ.get("S2_TIME_FIELD", "timestamp"),
    )

    periods = load_csv_to_singlestore(minio_cfg, db_cfg)
    for row in periods:
        ident, start, end, seconds = row
        print(f"{ident}: {start} -> {end} ({seconds} seconds)")


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()

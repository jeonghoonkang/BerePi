import json
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import streamlit as st
from minio import Minio


def get_client(endpoint: str, access_key: str, secret_key: str, secure: bool) -> Minio:
    """Return a MinIO client instance."""
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def list_csv_fields(client: Minio, bucket: str, prefix: str) -> List[Tuple[str, List[str]]]:
    """Return paths and field lists for all CSV files under the prefix."""
    results: List[Tuple[str, List[str]]] = []
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        if obj.object_name.lower().endswith(".csv"):
            response = client.get_object(bucket, obj.object_name)
            try:
                df = pd.read_csv(response, nrows=0)
                results.append((obj.object_name, list(df.columns)))
            finally:
                response.close()
                response.release_conn()
    return results


def field_stats(client: Minio, bucket: str, prefix: str, field: str) -> Tuple[int, int]:
    """Return total and missing counts for ``field`` across CSV files."""
    total = 0
    missing = 0
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        if obj.object_name.lower().endswith(".csv"):
            response = client.get_object(bucket, obj.object_name)
            try:
                try:
                    df = pd.read_csv(response, usecols=[field])
                except ValueError:
                    # Field missing from this file; skip it
                    continue
                total += len(df)
                missing += df[field].isna().sum()
            finally:
                response.close()
                response.release_conn()
    return total, missing


def load_config() -> dict:
    """Load connection settings from nocommit_minio.json.

    The configuration file is expected at the repository root and should
    contain ``endpoint``, ``access_key`` and ``secret_key`` keys. ``secure``
    is optional and defaults to ``False``.
    """

    cfg_path = Path(__file__).resolve().parents[2] / "nocommit_minio.json"
    try:
        with open(cfg_path) as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Configuration file not found: {cfg_path}")
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in {cfg_path}: {e}")
    return {}


st.title("MinIO CSV scanner")

config = load_config()
client = None
if config:
    client = get_client(
        config["endpoint"],
        config["access_key"],
        config["secret_key"],
        bool(config.get("secure", False)),
    )

fields_tab, stats_tab = st.tabs(["List fields", "Field stats"])

with fields_tab:
    bucket1 = st.text_input("Bucket", key="bucket1")
    prefix1 = st.text_input("Path prefix", key="prefix1")
    if st.button("Scan", key="scan_btn") and client and bucket1:
        for path, fields in list_csv_fields(client, bucket1, prefix1):
            st.write(f"**{path}**")
            st.write(", ".join(fields))

with stats_tab:
    bucket2 = st.text_input("Bucket", key="bucket2")
    prefix2 = st.text_input("Path prefix", key="prefix2")
    field_name = st.text_input("Field name")
    if st.button("Analyze", key="analyze_btn") and client and bucket2 and field_name:
        total, missing = field_stats(client, bucket2, prefix2, field_name)
        st.write(f"Total rows: {total}")
        st.write(f"Missing values: {missing}")
        if total:
            st.write(f"Missing ratio: {missing / total:.2%}")

import io
import json
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from minio import Minio
from streamlit.delta_generator import DeltaGenerator


def get_client(endpoint: str, access_key: str, secret_key: str, secure: bool) -> Minio:
    """Return a MinIO client instance."""
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


def list_csv_fields(
    client: Minio,
    bucket: str,
    prefix: str,
    progress: Optional[DeltaGenerator] = None,
    status: Optional[DeltaGenerator] = None,
) -> List[Tuple[str, List[str]]]:
    """Return paths and field lists for all CSV files under the prefix."""

    objs = [
        obj.object_name
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True)
        if obj.object_name.lower().endswith(".csv")
    ]

    total_files = len(objs)
    if status:
        status.text(f"0/{total_files}")
    if progress and not total_files:
        progress.progress(100)

    results: List[Tuple[str, List[str]]] = []
    out_path = Path(__file__).resolve().parent / "scanned_dirs.txt"
    written = set()
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, name in enumerate(objs, 1):
            directory = str(Path(name).parent)
            if directory not in written:
                f.write(f"{directory}\n")
                written.add(directory)

            response = client.get_object(bucket, name)
            try:
                df = pd.read_csv(response, nrows=0)
                results.append((name, list(df.columns)))
            finally:
                response.close()
                response.release_conn()

            if progress and total_files:
                progress.progress(int(idx / total_files * 100))
            if status:
                status.text(f"{idx}/{total_files}")

    return results


def field_stats(
    client: Minio,
    bucket: str,
    prefix: str,
    field: str,
    progress: Optional[DeltaGenerator] = None,
    status: Optional[DeltaGenerator] = None,
) -> Tuple[int, int]:
    """Return total and missing counts for ``field`` across CSV files."""

    objs = [
        obj.object_name
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True)
        if obj.object_name.lower().endswith(".csv")
    ]

    total_files = len(objs)
    if status:
        status.text(f"0/{total_files}")
    if progress and not total_files:
        progress.progress(100)

    total_rows = 0
    missing = 0
    out_path = Path(__file__).resolve().parent / "scanned_dirs.txt"
    written = set()
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, name in enumerate(objs, 1):
            directory = str(Path(name).parent)
            if directory not in written:
                f.write(f"{directory}\n")
                written.add(directory)

            response = client.get_object(bucket, name)
            try:
                try:
                    df = pd.read_csv(response, usecols=[field])
                except ValueError:
                    # Field missing from this file; skip it
                    continue
                total_rows += len(df)
                missing += df[field].isna().sum()
            finally:
                response.close()
                response.release_conn()

            if progress and total_files:
                progress.progress(int(idx / total_files * 100))
            if status:
                status.text(f"{idx}/{total_files}")

    return total_rows, missing


def copy_csv_without_field(
    client: Minio,
    src_bucket: str,
    src_object: str,
    field: str,
    dest_object: str,
    dest_bucket: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Copy ``src_object`` to ``dest_object`` without ``field``.

    Returns the original and resulting field lists for confirmation.
    """

    if not dest_bucket:
        dest_bucket = src_bucket

    response = client.get_object(src_bucket, src_object)
    try:
        df = pd.read_csv(response)
    finally:
        response.close()
        response.release_conn()

    original_fields = list(df.columns)
    if field not in df.columns:
        raise ValueError(
            f"Field '{field}' not found in {src_bucket}/{src_object}."
        )

    df = df.drop(columns=[field])
    csv_data = df.to_csv(index=False)
    data_bytes = csv_data.encode("utf-8")
    data_stream = io.BytesIO(data_bytes)

    client.put_object(
        dest_bucket,
        dest_object,
        data_stream,
        length=len(data_bytes),
        content_type="text/csv",
    )

    return original_fields, list(df.columns)


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
        msg = f"Configuration file not found: {cfg_path}"
        st.error(msg)
        required_fields = {
            "endpoint": "your-minio-endpoint:port",
            "access_key": "your-access-key",
            "secret_key": "your-secret-key",
            "secure": False,
        }
        st.write(
            "Create the file with the following JSON structure (the secure field is"
            " optional; set it to true if your deployment uses HTTPS):"
        )
        st.code(json.dumps(required_fields, indent=4), language="json")
        print(msg)
        print("Required configuration fields:")
        print(json.dumps(required_fields, indent=4))
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in {cfg_path}: {e}")
    return {}


st.title("MinIO CSV scanner")

config = load_config()
client = None
if config:
    secure = bool(config.get("secure", False))
    conn_msg = (
        f"Connecting to MinIO at {config['endpoint']} as {config['access_key']} "
        f"(secure={secure})"
    )
    st.write(conn_msg)
    print(conn_msg)
    client = get_client(
        config["endpoint"],
        config["access_key"],
        config["secret_key"],
        secure,
    )

fields_tab, stats_tab, modify_tab = st.tabs(
    ["List fields", "Field stats", "Copy without field"]
)

with fields_tab:
    bucket1 = st.text_input("Bucket", key="bucket1")
    prefix1 = st.text_input("Path prefix", key="prefix1")
    if st.button("Scan", key="scan_btn") and client and bucket1:
        progress = st.progress(0)
        status = st.empty()
        results = list_csv_fields(client, bucket1, prefix1, progress, status)
        for path, fields in results:
            st.write(f"**{path}**")
            st.write(", ".join(fields))

with stats_tab:
    bucket2 = st.text_input("Bucket", key="bucket2")
    prefix2 = st.text_input("Path prefix", key="prefix2")
    field_name = st.text_input("Field name")
    if st.button("Analyze", key="analyze_btn") and client and bucket2 and field_name:
        progress = st.progress(0)
        status = st.empty()
        total, missing = field_stats(
            client, bucket2, prefix2, field_name, progress, status
        )
        st.write(f"Total rows: {total}")
        st.write(f"Missing values: {missing}")
        if total:
            st.write(f"Missing ratio: {missing / total:.2%}")

with modify_tab:
    bucket3 = st.text_input("Source bucket", key="bucket3")
    object_path = st.text_input("CSV object path", key="object_path")
    field_to_remove = st.text_input("Field to remove", key="field_to_remove")
    dest_bucket = st.text_input(
        "Destination bucket (optional)", key="dest_bucket"
    )
    dest_object = st.text_input("Destination object name", key="dest_object")
    if st.button("Copy CSV without field", key="copy_btn") and client:
        if not bucket3 or not object_path or not field_to_remove or not dest_object:
            st.error(
                "Please provide bucket, object path, field, and destination object name."
            )
        else:
            try:
                original_fields, remaining_fields = copy_csv_without_field(
                    client,
                    bucket3,
                    object_path,
                    field_to_remove,
                    dest_object,
                    dest_bucket or None,
                )
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:  # pylint: disable=broad-except
                st.error(f"Failed to copy object: {exc}")
            else:
                target_bucket = dest_bucket or bucket3
                st.success(
                    f"Copied to {target_bucket}/{dest_object} with field '{field_to_remove}' removed."
                )
                st.write("Original fields:")
                st.write(", ".join(original_fields))
                st.write("Remaining fields:")
                st.write(", ".join(remaining_fields))
                print(
                    "Copied",
                    f"{bucket3}/{object_path} -> {target_bucket}/{dest_object}",
                    f"without field '{field_to_remove}'",
                )


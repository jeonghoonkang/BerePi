import argparse
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def ensure_packages(packages: Dict[str, str]) -> List[str]:
    """Install any packages that are missing locally."""

    missing = [
        package
        for module, package in packages.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print("Installing required packages:", ", ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    return missing


REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "streamlit": "streamlit",
    "minio": "minio",
}


INSTALLED_PACKAGES = ensure_packages(REQUIRED_PACKAGES)

import pandas as pd  # noqa: E402  # pylint: disable=wrong-import-position
import streamlit as st  # noqa: E402  # pylint: disable=wrong-import-position
from minio import Minio  # noqa: E402  # pylint: disable=wrong-import-position
from streamlit.delta_generator import DeltaGenerator  # noqa: E402  # pylint: disable=wrong-import-position

VENV_PATH_DISPLAY = "~/devel_opemnt/venv/bin"
print(f"Virtual environment path: {VENV_PATH_DISPLAY}")


def running_in_streamlit() -> bool:
    """Return ``True`` when executed through ``streamlit run``."""

    if getattr(st, "_is_running_with_streamlit", False):
        return True
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:  # pylint: disable=broad-except
        return False


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


def load_config(*, show_feedback: bool = True) -> dict:
    """Load connection settings from nocommit_minio.json.

    The configuration file is stored alongside this module in
    ``apps/minio/scan`` and should contain ``endpoint``, ``access_key`` and
    ``secret_key`` keys. ``secure`` is optional and defaults to ``False``.
    """

    cfg_path = Path(__file__).resolve().parent / "nocommit_minio.json"
    required_fields = {
        "endpoint": "your-minio-endpoint:port",
        "access_key": "your-access-key",
        "secret_key": "your-secret-key",
        "secure": False,
    }

    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(required_fields, indent=4), encoding="utf-8")
        message = (
            f"Configuration file not found. Created template configuration at {cfg_path}"
        )
        print(message)
        print("Required configuration fields:")
        print(json.dumps(required_fields, indent=4))
        if show_feedback:
            st.error(message)
            st.write(
                "Update the following values in the generated file (set secure to true if"
                " your deployment uses HTTPS):"
            )
            st.code(json.dumps(required_fields, indent=4), language="json")
        else:
            print(
                "Update the generated configuration file with your MinIO credentials and"
                " rerun the command."
            )
        return {}

    try:
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        error_msg = f"Invalid JSON in {cfg_path}: {exc}"
        print(error_msg)
        if show_feedback:
            st.error(error_msg)
        return {}


def run_streamlit_app() -> None:
    """Render the Streamlit interface."""

    st.title("MinIO CSV scanner")
    st.write(f"Virtual environment path: {VENV_PATH_DISPLAY}")

    if INSTALLED_PACKAGES:
        st.success(
            "Installed missing packages: " + ", ".join(sorted(set(INSTALLED_PACKAGES)))
        )

    config = load_config(show_feedback=True)
    if not config:
        return

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
        if st.button("Scan", key="scan_btn") and bucket1:
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
        if st.button("Analyze", key="analyze_btn") and bucket2 and field_name:
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
        if st.button("Copy CSV without field", key="copy_btn"):
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


def run_cli() -> None:
    """Provide a CLI alternative to the Streamlit interface."""

    parser = argparse.ArgumentParser(
        description=(
            "MinIO CSV utilities. Use `streamlit run main.py` for the web UI or the"
            " commands below for terminal usage."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list",
        help="List CSV files and show their fields",
    )
    list_parser.add_argument("bucket", help="Bucket name")
    list_parser.add_argument(
        "prefix",
        nargs="?",
        default="",
        help="Prefix path to scan (defaults to entire bucket)",
    )

    stats_parser = subparsers.add_parser(
        "stats",
        help="Show total rows and missing values for a field",
    )
    stats_parser.add_argument("bucket", help="Bucket name")
    stats_parser.add_argument("field", help="Field/column to analyze")
    stats_parser.add_argument(
        "prefix",
        nargs="?",
        default="",
        help="Prefix path to scan (defaults to entire bucket)",
    )

    copy_parser = subparsers.add_parser(
        "copy",
        help="Copy a CSV object while removing a column",
    )
    copy_parser.add_argument("src_bucket", help="Source bucket")
    copy_parser.add_argument("src_object", help="Source CSV object path")
    copy_parser.add_argument("field", help="Field/column to remove")
    copy_parser.add_argument("dest_object", help="Destination object path")
    copy_parser.add_argument(
        "--dest-bucket",
        dest="dest_bucket",
        help="Destination bucket (defaults to the source bucket)",
    )

    args = parser.parse_args()

    if INSTALLED_PACKAGES:
        print(
            "Installed missing packages:", ", ".join(sorted(set(INSTALLED_PACKAGES)))
        )

    config = load_config(show_feedback=False)
    if not config:
        return

    secure = bool(config.get("secure", False))
    conn_msg = (
        f"Connecting to MinIO at {config['endpoint']} as {config['access_key']} "
        f"(secure={secure})"
    )
    print(conn_msg)
    client = get_client(
        config["endpoint"],
        config["access_key"],
        config["secret_key"],
        secure,
    )

    if args.command == "list":
        results = list_csv_fields(client, args.bucket, args.prefix)
        if results:
            for path, fields in results:
                print(f"{path}: {', '.join(fields)}")
            print(
                "Scanned directory list written to",
                Path(__file__).resolve().parent / "scanned_dirs.txt",
            )
        else:
            print("No CSV files found for the provided bucket and prefix.")
    elif args.command == "stats":
        total, missing = field_stats(client, args.bucket, args.prefix, args.field)
        print(f"Total rows: {total}")
        print(f"Missing values: {missing}")
        if total:
            print(f"Missing ratio: {missing / total:.2%}")
    elif args.command == "copy":
        try:
            original_fields, remaining_fields = copy_csv_without_field(
                client,
                args.src_bucket,
                args.src_object,
                args.field,
                args.dest_object,
                args.dest_bucket,
            )
        except ValueError as exc:
            print(f"Error: {exc}")
            return
        print(
            "Copied",
            f"{args.src_bucket}/{args.src_object} -> {(args.dest_bucket or args.src_bucket)}/{args.dest_object}",
            f"without field '{args.field}'",
        )
        print("Original fields:", ", ".join(original_fields))
        print("Remaining fields:", ", ".join(remaining_fields))
    else:
        parser.print_help()


if running_in_streamlit():
    run_streamlit_app()
elif __name__ == "__main__":
    run_cli()

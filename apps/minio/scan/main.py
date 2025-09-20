import argparse
import importlib.util
import io
import json
import ssl as ssl_lib
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
    "urllib3": "urllib3",

}


INSTALLED_PACKAGES = ensure_packages(REQUIRED_PACKAGES)

import pandas as pd  # noqa: E402  # pylint: disable=wrong-import-position
import streamlit as st  # noqa: E402  # pylint: disable=wrong-import-position
import urllib3  # noqa: E402  # pylint: disable=wrong-import-position
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


def parse_bool(value: Any, default: bool = False) -> bool:
    """Convert a configuration value into a boolean."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _normalize_path(value: Any) -> Optional[str]:
    """Return a trimmed path string or ``None``."""

    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def resolve_ssl_options(
    config: dict,
) -> Tuple[bool, Dict[str, Any], Optional[urllib3.PoolManager], bool]:
    """Normalize SSL options and prepare an optional HTTP client."""

    secure = parse_bool(config.get("secure"), False)
    ssl_config: Dict[str, Any] = {
        "enabled": False,
        "cert_check": True,
        "ca_file": None,
        "cert_file": None,
        "key_file": None,
    }

    raw_ssl = config.get("ssl")
    if isinstance(raw_ssl, dict):
        ssl_config["enabled"] = parse_bool(raw_ssl.get("enabled"), False)
        ssl_config["cert_check"] = parse_bool(raw_ssl.get("cert_check"), True)
        ssl_config["ca_file"] = _normalize_path(raw_ssl.get("ca_file"))
        ssl_config["cert_file"] = _normalize_path(raw_ssl.get("cert_file"))
        ssl_config["key_file"] = _normalize_path(raw_ssl.get("key_file"))

    has_custom_ssl_material = any(
        ssl_config[name] for name in ("ca_file", "cert_file", "key_file")
    )
    if has_custom_ssl_material and not ssl_config["enabled"]:
        ssl_config["enabled"] = True

    secure = secure or ssl_config["enabled"]
    cert_check = ssl_config["cert_check"]
    http_client: Optional[urllib3.PoolManager] = None
    if ssl_config["enabled"] and has_custom_ssl_material:
        pool_kwargs: Dict[str, Any] = {
            "cert_reqs": (
                ssl_lib.CERT_REQUIRED if cert_check else ssl_lib.CERT_NONE
            )
        }
        if ssl_config["ca_file"]:
            pool_kwargs["ca_certs"] = ssl_config["ca_file"]
        if ssl_config["cert_file"]:
            pool_kwargs["cert_file"] = ssl_config["cert_file"]
        if ssl_config["key_file"]:
            pool_kwargs["key_file"] = ssl_config["key_file"]
        http_client = urllib3.PoolManager(**pool_kwargs)

    return secure, ssl_config, http_client, cert_check


def format_ssl_display(ssl_config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a user-friendly representation of SSL settings."""

    return {
        "enabled": ssl_config.get("enabled", False),
        "cert_check": ssl_config.get("cert_check", True),
        "ca_file": ssl_config.get("ca_file") or "(system default)",
        "cert_file": ssl_config.get("cert_file") or "(not set)",
        "key_file": ssl_config.get("key_file") or "(not set)",
    }


def get_client(
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool,
    *,
    http_client: Optional[urllib3.PoolManager] = None,
    cert_check: bool = True,
) -> Minio:
    """Return a MinIO client instance."""

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        http_client=http_client,
        cert_check=cert_check,
    )



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
    """Load connection settings from ``nocommit_minio.json``.

    The configuration file is stored alongside this module in
    ``apps/minio/scan`` and should contain ``endpoint``, ``access_key`` and
    ``secret_key`` keys. ``secure`` toggles HTTPS and defaults to ``False``.
    For deployments that require custom TLS certificates, add an ``ssl``
    section with ``enabled``, ``cert_check``, ``ca_file``, ``cert_file`` and
    ``key_file`` entries.
    """

    cfg_path = Path(__file__).resolve().parent / "nocommit_minio.json"
    template_config = {

        "endpoint": "your-minio-endpoint:port",
        "access_key": "your-access-key",
        "secret_key": "your-secret-key",
        "secure": False,
        "ssl": {
            "enabled": False,
            "cert_check": True,
            "ca_file": "path/to/ca.pem",
            "cert_file": "path/to/client.crt",
            "key_file": "path/to/client.key",
        },
    }

    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(template_config, indent=4), encoding="utf-8")

        message = (
            f"Configuration file not found. Created template configuration at {cfg_path}"
        )
        print(message)
        print("Required configuration fields:")

        print(json.dumps(template_config, indent=4))
        if show_feedback:
            st.error(message)
            st.write(
                "Update the following values in the generated file (set secure to true if"
                " your deployment uses HTTPS, and enable the ssl block when you use"
                " custom certificates):"
            )
            st.code(json.dumps(template_config, indent=4), language="json")
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


    secure, ssl_config, http_client, cert_check = resolve_ssl_options(config)
    conn_msg = (
        f"Connecting to MinIO at {config['endpoint']} as {config['access_key']} "
        f"(secure={secure}, cert_check={cert_check})"
    )
    st.write(conn_msg)
    print(conn_msg)
    if config.get("ssl") is not None:
        ssl_display = format_ssl_display(ssl_config)
        st.write("SSL options:")
        st.json(ssl_display)
        print("SSL options:", ssl_display)
    client = get_client(
        config["endpoint"],
        config["access_key"],
        config["secret_key"],
        secure,

        http_client=http_client,
        cert_check=cert_check,
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


    secure, ssl_config, http_client, cert_check = resolve_ssl_options(config)
    conn_msg = (
        f"Connecting to MinIO at {config['endpoint']} as {config['access_key']} "
        f"(secure={secure}, cert_check={cert_check})"
    )
    print(conn_msg)
    if config.get("ssl") is not None:
        print("SSL options:", format_ssl_display(ssl_config))

    client = get_client(
        config["endpoint"],
        config["access_key"],
        config["secret_key"],
        secure,

        http_client=http_client,
        cert_check=cert_check,
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

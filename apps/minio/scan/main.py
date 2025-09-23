import argparse
import os
import importlib.util
import io
import json
import ssl as ssl_lib
import subprocess
import sys
from dataclasses import dataclass
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
from minio.error import S3Error  # noqa: E402  # pylint: disable=wrong-import-position
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


def _normalize_bucket(value: Any) -> str:
    """Return a sanitized bucket value or an empty string."""

    if isinstance(value, str):
        return value.strip()
    return ""


def _normalize_prefix(value: Any) -> str:
    """Return a sanitized prefix value or an empty string."""

    if isinstance(value, str):
        return value.strip()
    return ""


def resolve_ssl_options(
    config: dict,
) -> Tuple[bool, Optional[urllib3.PoolManager], bool]:
    """Normalize SSL options and prepare an optional HTTP client."""

    # 강제로 HTTP 사용 (secure=False)
    secure = False
    
    # SSL 설정을 처리하지 않음 - 기본값만 사용
    cert_check = True
    http_client: Optional[urllib3.PoolManager] = None

    return secure, http_client, cert_check


def format_ssl_display(ssl_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a safe, UI-friendly summary of SSL options.

    - Coerces booleans using existing helpers
    - Summarizes file paths by existence and readability, without reading files
    """

    if not isinstance(ssl_config, dict):
        return {"enabled": False}

    enabled = parse_bool(ssl_config.get("enabled"), False)
    cert_check = parse_bool(ssl_config.get("cert_check"), True)

    def summarize_path(value: Any) -> Dict[str, Any]:
        norm = _normalize_path(value)
        if not norm:
            return {"set": False}
        p = Path(norm).expanduser()
        exists = p.exists()
        is_file = p.is_file() if exists else False
        readable = os.access(p, os.R_OK) if exists else False
        return {
            "set": True,
            "path": str(p),
            "exists": exists,
            "is_file": is_file,
            "readable": readable,
        }

    return {
        "enabled": enabled,
        "cert_check": cert_check,
        "ca_file": summarize_path(ssl_config.get("ca_file")),
        "cert_file": summarize_path(ssl_config.get("cert_file")),
        "key_file": summarize_path(ssl_config.get("key_file")),
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



def verify_minio_connection(
    client: Minio, bucket: Optional[str] = None
) -> Tuple[bool, str, str]:
    """Check whether a MinIO connection is usable."""

    try:
        if bucket:
            if not client.bucket_exists(bucket):
                return (
                    False,
                    f"Bucket '{bucket}' does not exist or access is denied.",
                    "error",
                )
            return (
                True,
                f"Successfully connected to MinIO and verified bucket '{bucket}'.",
                "success",
            )
        client.list_buckets()
        return True, "Successfully connected to MinIO.", "success"
    except S3Error as exc:  # pragma: no cover - network failure paths
        if not bucket and exc.code == "AccessDenied":
            return (
                True,
                "Connected to MinIO but bucket listing is not permitted for the provided credentials.",
                "warning",
            )
        return (
            False,
            f"Failed to connect to MinIO: {exc.code} - {exc.message}",
            "error",
        )
    except urllib3.exceptions.HTTPError as exc:  # pragma: no cover - network failure paths
        return False, f"Failed to connect to MinIO: {exc}", "error"
    except Exception as exc:  # pragma: no cover - network failure paths
        return False, f"Failed to connect to MinIO: {exc}", "error"


_HTTPS_REQUIRED_TOKEN = "client sent an http request to an https server"
_API_PORT_HINT_TOKEN = "s3 api requests must be made to api port"


def _should_retry_with_https(message: str) -> bool:
    """Return ``True`` when the error indicates HTTPS is required."""

    return _HTTPS_REQUIRED_TOKEN in message.lower()


def _indicates_console_port(message: str) -> bool:
    """Return ``True`` when the error suggests the console port was used."""

    return _API_PORT_HINT_TOKEN in message.lower()


def _suggest_api_port(port: Optional[int]) -> Optional[int]:
    """Suggest S3 API port for a known console port (e.g., 9001 -> 9000)."""

    if port is None:
        return None
    mapping = {9001: 9000, 9090: 9000}
    return mapping.get(port)


def _parse_int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int,)):
            return int(value)
        if isinstance(value, str):
            v = value.strip()
            if v.startswith("+") or v.startswith("-"):
                if v[1:].isdigit():
                    return int(v)
            elif v.isdigit():
                return int(v)
        return None
    except Exception:
        return None


def _extract_host_port(endpoint: str, explicit_port: Any) -> Tuple[str, Optional[int]]:
    """Return (host, port) where host excludes port if present.

    If `explicit_port` is provided and valid, it takes precedence.
    """

    host = (endpoint or "").strip()
    port = _parse_int(explicit_port)
    if port is not None:
        # Ensure host has no trailing :port
        if ":" in host and host.rsplit(":", 1)[-1].isdigit():
            host = host.rsplit(":", 1)[0]
        return host, port

    if ":" in host:
        h, p = host.rsplit(":", 1)
        if p.isdigit():
            return h, int(p)
    return host, None


def _compose_endpoint(host: str, port: Optional[int]) -> str:
    return f"{host}:{port}" if port is not None else host


@dataclass
class ConnectionAttempt:
    """Details about a MinIO connection attempt."""

    client: Optional[Minio]
    secure: bool
    success: bool
    level: str
    message: str
    fallback_attempted: bool = False
    initial_error: Optional[str] = None
    # Port/endpoint fallback (e.g., console -> API port)
    endpoint_used: Optional[str] = None
    endpoint_fallback_attempted: bool = False
    endpoint_initial_error: Optional[str] = None

    @property
    def is_viable(self) -> bool:
        """Return ``True`` when the connection can be used."""

        return self.success or self.level == "warning"


def establish_connection(
    config: dict,
    secure: bool,
    http_client: Optional[urllib3.PoolManager],
    cert_check: bool,
    bucket: Optional[str],
) -> ConnectionAttempt:
    """Create a MinIO client and ensure the connection works."""

    # Build endpoint from host + (optional) port field
    host, port = _extract_host_port(config.get("endpoint", ""), config.get("port"))
    endpoint = _compose_endpoint(host, port)
    client = get_client(
        endpoint,
        config["access_key"],
        config["secret_key"],
        secure,
        http_client=http_client,
        cert_check=cert_check,
    )
    success, message, level = verify_minio_connection(client, bucket)
    if success or level == "warning":
        return ConnectionAttempt(
            client=client,
            secure=secure,
            success=success,
            level=level,
            message=message,
            endpoint_used=endpoint,
        )

    if not secure and _should_retry_with_https(message):
        fallback_client = get_client(
            endpoint,
            config["access_key"],
            config["secret_key"],
            True,
            http_client=http_client,
            cert_check=cert_check,
        )
        fallback_success, fallback_message, fallback_level = verify_minio_connection(
            fallback_client, bucket
        )
        fallback_viable = fallback_success or fallback_level == "warning"
        return ConnectionAttempt(
            client=fallback_client if fallback_viable else None,
            secure=True,
            success=fallback_success,
            level=fallback_level,
            message=fallback_message,
            fallback_attempted=True,
            initial_error=message,
            endpoint_used=endpoint if fallback_viable else None,
        )

    # Detect console-port usage and retry on common API port
    if _indicates_console_port(message):
        new_port = _suggest_api_port(port)
        if new_port is None:
            # Try default mapping from known console port 9001 if no port detected
            new_port = 9000
        new_endpoint = _compose_endpoint(host, new_port)
        if new_endpoint and new_endpoint != endpoint:
            api_client = get_client(
                new_endpoint,
                config["access_key"],
                config["secret_key"],
                secure,
                http_client=http_client,
                cert_check=cert_check,
            )
            api_success, api_message, api_level = verify_minio_connection(
                api_client, bucket
            )
            api_viable = api_success or api_level == "warning"
            if api_viable:
                return ConnectionAttempt(
                    client=api_client,
                    secure=secure,
                    success=api_success,
                    level=api_level,
                    message=api_message,
                    endpoint_fallback_attempted=True,
                    endpoint_initial_error=message,
                    endpoint_used=new_endpoint,
                )
            # Try HTTPS on API port if HTTP failed with TLS-required hint
            if not secure and _should_retry_with_https(api_message):
                https_client = get_client(
                    new_endpoint,
                    config["access_key"],
                    config["secret_key"],
                    True,
                    http_client=http_client,
                    cert_check=cert_check,
                )
                https_ok, https_msg, https_level = verify_minio_connection(
                    https_client, bucket
                )
                https_viable = https_ok or https_level == "warning"
                return ConnectionAttempt(
                    client=https_client if https_viable else None,
                    secure=True,
                    success=https_ok,
                    level=https_level,
                    message=https_msg,
                    fallback_attempted=True,
                    initial_error=api_message,
                    endpoint_fallback_attempted=True,
                    endpoint_initial_error=message,
                    endpoint_used=new_endpoint if https_viable else None,
                )

    return ConnectionAttempt(
        client=None,
        secure=secure,
        success=success,
        level=level,
        message=message,
        endpoint_used=endpoint,
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


def load_config(*, show_feedback: bool = True, quiet: bool = False) -> dict:
    """Load connection settings from ``nocommit_minio.json``.

    The configuration file is stored alongside this module in
    ``apps/minio/scan`` and should contain ``endpoint``, ``access_key`` and
    ``secret_key`` keys. ``secure`` toggles HTTPS and defaults to ``False``.
    ``bucket`` and ``prefix`` provide optional defaults that are applied to the
    CLI commands and Streamlit UI. For deployments that require custom TLS
    certificates, add an ``ssl`` section with ``enabled``, ``cert_check``,
    ``ca_file``, ``cert_file`` and ``key_file`` entries.
    """

    cfg_path = Path(__file__).resolve().parent / "nocommit_minio.json"
    template_config = {

        "endpoint": "your-minio-endpoint",
        "port": 9000,
        "access_key": "your-access-key",
        "secret_key": "your-secret-key",
        "secure": False,
        "bucket": "your-bucket-name",
        "prefix": "optional/path/prefix/",
        "ssl": {
            "enabled": False,
            "cert_check": True,
            "ca_file": "path/to/ca.pem",
            "cert_file": "path/to/client.crt",
            "key_file": "path/to/client.key",
        },
    }

    if not cfg_path.exists():
        if quiet:
            return {}
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
            config = json.load(f)
    except json.JSONDecodeError as exc:
        if quiet:
            return {}
        error_msg = f"Invalid JSON in {cfg_path}: {exc}"
        print(error_msg)
        if show_feedback:
            st.error(error_msg)
        return {}

    config["bucket"] = _normalize_bucket(config.get("bucket"))
    config["prefix"] = _normalize_prefix(config.get("prefix"))

    return config


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

    bucket_default = config.get("bucket", "") or ""
    prefix_default = config.get("prefix", "") or ""

    secure, http_client, cert_check = resolve_ssl_options(config)
    connection = establish_connection(
        config,
        secure,
        http_client,
        cert_check,
        bucket_default or None,
    )
    # Show composed endpoint (host + port if provided)
    host, port = _extract_host_port(config.get("endpoint", ""), config.get("port"))
    display_endpoint = _compose_endpoint(host, port)
    active_scheme = "https" if connection.secure else "http"
    conn_msg = (
        f"Connecting to MinIO at {display_endpoint} via {active_scheme.upper()} "
        f"as {config['access_key']} (secure={connection.secure}, cert_check={cert_check})"
    )
    st.write(conn_msg)
    print(conn_msg)
    configured_scheme = "https" if secure else "http"
    config_summary = (
        "Configured defaults -> secure="
        f"{secure} ({configured_scheme}), bucket={bucket_default or '(not set)'}, "

        f"prefix={prefix_default or '(not set)'}"
    )
    st.info(config_summary)
    print(config_summary)
    if config.get("ssl") is not None:
        ssl_display = format_ssl_display(config.get("ssl"))
        st.write("SSL options:")
        st.json(ssl_display)
        print("SSL options:", ssl_display)
    if connection.endpoint_fallback_attempted and connection.endpoint_initial_error:
        st.warning(
            "Endpoint appears to be the Console port. Retried on API port. "
            "Update 'port' in nocommit_minio.json to the S3 API port (e.g., 9000)."
        )
        st.write(f"Connected using adjusted endpoint: {connection.endpoint_used}")
        print(
            "Retried on API port due to console-port error; "
            f"using endpoint {connection.endpoint_used}."
        )
    if connection.fallback_attempted and connection.initial_error:
        fallback_lines = [
            "Initial HTTP connection attempt failed:",
            connection.initial_error,
            'Retried with HTTPS because the server requires TLS. Update "secure": true in nocommit_minio.json to avoid this retry.',
        ]
        fallback_message = "\n".join(fallback_lines)
        st.warning(fallback_message)
        print(fallback_message)
    if connection.level == "warning":
        st.warning(connection.message)
        print(f"Warning: {connection.message}")
    elif connection.success:
        st.success(connection.message)
        print(connection.message)
    else:
        st.error(connection.message)
        print(connection.message)
        return

    if not connection.client:
        return

    client = connection.client


    connection_ok, connection_message, level = verify_minio_connection(
        client, bucket_default or None
    )
    if level == "warning":
        st.warning(connection_message)
        print(f"Warning: {connection_message}")
    elif connection_ok:
        st.success(connection_message)
        print(connection_message)
    else:
        st.error(connection_message)
        print(connection_message)
        return

    fields_tab, stats_tab, modify_tab = st.tabs(
        ["List fields", "Field stats", "Copy without field"]
    )

    with fields_tab:
        bucket1 = st.text_input("Bucket", value=bucket_default, key="bucket1")
        prefix1 = st.text_input(
            "Path prefix", value=prefix_default, key="prefix1"
        )
        if st.button("Scan", key="scan_btn") and bucket1:
            progress = st.progress(0)
            status = st.empty()
            results = list_csv_fields(client, bucket1, prefix1, progress, status)
            for path, fields in results:
                st.write(f"**{path}**")
                st.write(", ".join(fields))

    with stats_tab:
        bucket2 = st.text_input("Bucket", value=bucket_default, key="bucket2")
        prefix2 = st.text_input(
            "Path prefix", value=prefix_default, key="prefix2"
        )
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
        bucket3 = st.text_input(
            "Source bucket", value=bucket_default, key="bucket3"
        )
        object_path = st.text_input("CSV object path", key="object_path")
        field_to_remove = st.text_input("Field to remove", key="field_to_remove")
        dest_bucket = st.text_input(
            "Destination bucket (optional)",
            value=bucket_default,
            key="dest_bucket",
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

    prog_name = Path(__file__).name
    parser = argparse.ArgumentParser(
        prog=prog_name,
        description=(
            "MinIO CSV utilities. Use `streamlit run main.py` for the web UI or the"
            " commands below for terminal usage."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["connect", "list", "stats", "copy"],
        help="Command to execute",
    )
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Arguments for the selected command",
    )
    parsed = parser.parse_args()


    is_connect_cmd = parsed.command == "connect"

    if INSTALLED_PACKAGES and not is_connect_cmd:
        print(
            "Installed missing packages:", ", ".join(sorted(set(INSTALLED_PACKAGES)))
        )

    config = load_config(show_feedback=False, quiet=is_connect_cmd)
    if not config:
        if is_connect_cmd:
            print(
                "FAILED: Configuration missing or invalid. "
                "Please configure apps/minio/scan/nocommit_minio.json"
            )
        return

    bucket_default = config.get("bucket", "") or ""
    prefix_default = config.get("prefix", "") or ""

    secure, http_client, cert_check = resolve_ssl_options(config)
    try:
        connection = establish_connection(
            config,
            secure,
            http_client,
            cert_check,
            bucket_default or None,
        )
    except KeyError as exc:
        if is_connect_cmd:
            print(f"FAILED: Missing required config key: {exc}")
            return
        else:
            print(f"Configuration error: missing key {exc}")
            return
    host, port = _extract_host_port(config.get("endpoint", ""), config.get("port"))
    display_endpoint = _compose_endpoint(host, port)
    if is_connect_cmd:
        # Minimal connectivity check output
        if connection.is_viable and connection.client:
            print("SUCCESS: Connected to MinIO.")
        else:
            print(f"FAILED: {connection.message}")
        return
    else:
        active_scheme = "https" if connection.secure else "http"
        conn_msg = (
            f"Connecting to MinIO at {display_endpoint} via {active_scheme.upper()} "
            f"as {config['access_key']} (secure={connection.secure}, cert_check={cert_check})"
        )
        print(conn_msg)
        configured_scheme = "https" if secure else "http"
        config_summary = (
            f"Configured defaults -> secure={secure} ({configured_scheme}), "

            f"bucket={bucket_default or '(not set)'}, "
            f"prefix={prefix_default or '(not set)'}"
        )
        print(config_summary)
        if config.get("ssl") is not None:
            print("SSL options:", format_ssl_display(config.get("ssl")))
        if connection.endpoint_fallback_attempted and connection.endpoint_initial_error:
            print(
                "Endpoint seems to be the Console port. Retried on API port. "
                "Please update 'port' in nocommit_minio.json to the S3 API port (e.g., 9000)."
            )
            if connection.endpoint_used:
                print(f"Adjusted endpoint used: {connection.endpoint_used}")
        if connection.fallback_attempted and connection.initial_error:
            fallback_lines = [
                "Initial HTTP connection attempt failed:",
                connection.initial_error,
                'Retried with HTTPS because the server requires TLS. Update "secure": true in nocommit_minio.json to avoid this retry.',
            ]
            print("\n".join(fallback_lines))
        if connection.level == "warning":
            print(f"Warning: {connection.message}")
        else:
            print(connection.message)
        if not connection.is_viable or not connection.client:
            return

    client = connection.client

    if not parsed.command:
        parser.print_help()
        return

    command_args = parsed.command_args


    if parsed.command == "connect":
        # Already handled above; keep for completeness
        return
    elif parsed.command == "list":
        list_parser = argparse.ArgumentParser(
            prog=f"{prog_name} list",
            description="List CSV files and show their fields.",
        )
        list_parser.add_argument(
            "bucket",
            nargs="?",
            default=None,
            help="Bucket name (defaults to the value from nocommit_minio.json)",
        )
        list_parser.add_argument(
            "prefix",
            nargs="?",
            default=None,
            help="Prefix path to scan (defaults to the value from nocommit_minio.json)",
        )
        list_args = list_parser.parse_args(command_args)
        bucket = list_args.bucket if list_args.bucket not in (None, "") else bucket_default
        prefix = (
            list_args.prefix if list_args.prefix is not None else prefix_default
        )
        if not bucket:
            print(
                "Bucket must be provided either in nocommit_minio.json or as an argument."
            )
            return
        prefix = prefix or ""
        print(
            f"Using bucket='{bucket}', prefix='{prefix or '(none)'}' for list command."
        )
        results = list_csv_fields(client, bucket, prefix)
        if results:
            for path, fields in results:
                print(f"{path}: {', '.join(fields)}")
            print(
                "Scanned directory list written to",
                Path(__file__).resolve().parent / "scanned_dirs.txt",
            )
        else:
            print("No CSV files found for the provided bucket and prefix.")
    elif parsed.command == "stats":
        stats_parser = argparse.ArgumentParser(
            prog=f"{prog_name} stats",
            description="Show total rows and missing values for a field.",
        )
        stats_parser.add_argument(
            "--bucket",
            dest="bucket_option",
            help="Override the bucket (defaults to the value from nocommit_minio.json)",
        )
        stats_parser.add_argument(
            "--prefix",
            dest="prefix_option",
            help="Override the prefix (defaults to the value from nocommit_minio.json)",
        )
        stats_parser.add_argument(
            "--field",
            dest="field_option",
            help="Field/column to analyze (alternative to positional argument)",
        )
        stats_parser.add_argument(
            "positionals",
            nargs="*",
            help="Positional arguments: [bucket] field [prefix]",
        )
        stats_args = stats_parser.parse_args(command_args)

        bucket = stats_args.bucket_option or bucket_default
        prefix = (
            stats_args.prefix_option
            if stats_args.prefix_option is not None
            else prefix_default
        )
        field = stats_args.field_option
        positionals = stats_args.positionals

        if positionals:
            if len(positionals) == 1:
                if stats_args.bucket_option is not None or bucket_default:
                    field = field or positionals[0]
                else:
                    bucket = positionals[0]
            elif len(positionals) == 2:
                if stats_args.bucket_option is not None:
                    field = field or positionals[0]
                    if stats_args.prefix_option is None:
                        prefix = positionals[1]
                else:
                    bucket = positionals[0]
                    field = field or positionals[1]
            else:
                bucket = positionals[0]
                field = field or positionals[1]
                if stats_args.prefix_option is None:
                    prefix = " ".join(positionals[2:])

        if not bucket:
            print(
                "Bucket must be provided either in nocommit_minio.json or as an argument."
            )
            return
        if not field:
            print(
                "Field name is required. Provide it as a positional argument or via --field."
            )
            return

        prefix = prefix or ""
        print(
            f"Using bucket='{bucket}', prefix='{prefix or '(none)'}', field='{field}' for stats command."
        )
        total, missing = field_stats(client, bucket, prefix, field)
        print(f"Total rows: {total}")
        print(f"Missing values: {missing}")
        if total:
            print(f"Missing ratio: {missing / total:.2%}")
    elif parsed.command == "copy":
        copy_parser = argparse.ArgumentParser(
            prog=f"{prog_name} copy",
            description="Copy a CSV object while removing a column.",
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
        copy_args = copy_parser.parse_args(command_args)
        try:
            original_fields, remaining_fields = copy_csv_without_field(
                client,
                copy_args.src_bucket,
                copy_args.src_object,
                copy_args.field,
                copy_args.dest_object,
                copy_args.dest_bucket,
            )
        except ValueError as exc:
            print(f"Error: {exc}")
            return
        print(
            "Copied",
            f"{copy_args.src_bucket}/{copy_args.src_object} -> {(copy_args.dest_bucket or copy_args.src_bucket)}/{copy_args.dest_object}",
            f"without field '{copy_args.field}'",
        )
        print("Original fields:", ", ".join(original_fields))
        print("Remaining fields:", ", ".join(remaining_fields))
    else:
        parser.print_help()


if running_in_streamlit():
    run_streamlit_app()
elif __name__ == "__main__":
    run_cli()

"""Connection diagnostics for the MinIO configuration used by ``main.py``.

This helper mirrors the CLI connection logic and records detailed results in
``err_connect.txt`` so operators can review failures after the fact.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import List

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main import (  # type: ignore[attr-defined]
    INSTALLED_PACKAGES,
    establish_connection,
    load_config,
    resolve_ssl_options,
)


LOG_FILE = Path(__file__).resolve().parent / "err_connect.txt"


def _write_log(lines: List[str]) -> None:
    """Persist the diagnostic output."""

    LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append(lines: List[str], message: str) -> None:
    lines.append(message)
    print(message)


def main() -> int:
    """Execute the connection diagnostic routine."""

    lines: List[str] = [
        f"[{datetime.now().isoformat(timespec='seconds')}] MinIO connection test",
    ]

    if INSTALLED_PACKAGES:
        _append(
            lines,
            "Installed missing packages: "
            + ", ".join(sorted(set(INSTALLED_PACKAGES))),
        )

    config = load_config(show_feedback=False)
    if not config:
        _append(lines, "Failed to load MinIO configuration from nocommit_minio.json.")
        _write_log(lines)
        return 1

    bucket_default = config.get("bucket", "") or ""
    prefix_default = config.get("prefix", "") or ""

    secure, ssl_config, http_client, cert_check = resolve_ssl_options(config)
    configured_scheme = "https" if secure else "http"
    _append(
        lines,
        "Configured defaults -> secure="
        f"{secure} ({configured_scheme}), bucket={bucket_default or '(not set)'}, "
        f"prefix={prefix_default or '(not set)'}",
    )

    bucket = bucket_default or None

    try:
        attempt = establish_connection(
            config,
            secure,
            http_client,
            cert_check,
            bucket,
        )
    except Exception as exc:  # pragma: no cover - network failure paths
        _append(lines, f"Unexpected exception while connecting to MinIO: {exc!r}")
        _write_log(lines)
        return 1

    active_scheme = "https" if attempt.secure else "http"
    _append(
        lines,
        "Attempted connection -> "
        f"endpoint={config['endpoint']} via {active_scheme.upper()} as {config['access_key']} "
        f"(secure={attempt.secure}, cert_check={cert_check})",
    )

    if config.get("ssl") is not None:
        ssl_summary = {
            "enabled": ssl_config.get("enabled", False),
            "cert_check": ssl_config.get("cert_check", True),
            "ca_file": ssl_config.get("ca_file") or "(system default)",
            "cert_file": ssl_config.get("cert_file") or "(not set)",
            "key_file": ssl_config.get("key_file") or "(not set)",
        }
        _append(lines, f"SSL options: {ssl_summary}")

    if attempt.fallback_attempted:
        _append(lines, "HTTP connection failed; attempted HTTPS fallback.")
        if attempt.initial_error:
            _append(lines, f"Initial error: {attempt.initial_error}")

    status_prefix = "Success" if attempt.is_viable else "Error"
    _append(lines, f"{status_prefix}: {attempt.message}")

    _write_log(lines)
    return 0 if attempt.is_viable else 1



if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Register over HTTPS; stdout contains only validated device.env assignments."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_REGISTER_PATH = "/v1/devices/register"
DEFAULT_MANUAL_PATH = "/v1/devices/manual"


def endpoint_url(server_url: str, api_path: str) -> str:
    parsed = urlsplit(server_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or
            any(character.isspace() for character in server_url) or "\\" in server_url):
        raise ValueError("ID server must be an HTTPS URL without credentials/query/fragment")
    # Accessing .port also validates the port number before any state or request is created.
    _ = parsed.port
    if (not re.fullmatch(r"/[A-Za-z0-9._~/-]*", api_path) or "//" in api_path or
            any(segment in (".", "..") for segment in api_path.split("/"))):
        raise ValueError("ID API path must start with / and contain no host, query, or dot segments")
    # Append to any reverse-proxy prefix in the base URL; never let a path replace the host.
    return server_url.rstrip("/") + api_path


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward enrollment credentials to a redirected host/path.
        return None


def identity_key(state_path: Path, server_url: str) -> str:
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if not isinstance(state, dict) or state.get("server_url") != server_url:
            raise ValueError("Registration state belongs to a different Fleet server")
        key = state.get("registration_key", "")
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("Invalid registration state; restore this device's backup")
        return key
    key = secrets.token_hex(32)
    descriptor, temporary = tempfile.mkstemp(prefix=".registration-", dir=state_path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump({"server_url": server_url, "registration_key": key}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, state_path)
        # Persist the directory entry before sending a request, including after power loss.
        directory = os.open(state_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return key


def register(server_url: str, enrollment_token: str, state_path: Path,
             requested_id: str | None = None, *,
             registration_path: str = DEFAULT_REGISTER_PATH,
             manual_path: str = DEFAULT_MANUAL_PATH) -> dict[str, str]:
    server_url = server_url.rstrip("/")
    url = endpoint_url(server_url, registration_path if requested_id is None else manual_path)
    if len(enrollment_token) < 32 or enrollment_token.startswith("CHANGE_ME"):
        raise ValueError("Set FLEET_ENROLLMENT_TOKEN to the server's enrollment secret")
    if requested_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", requested_id):
        raise ValueError("Invalid manually entered device ID")
    state_path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    # Serialize standalone invocations too, so they cannot create different local keys.
    lock_fd = os.open(str(state_path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if requested_id is None:
            payload = {"registration_key": identity_key(state_path, server_url)}
        else:
            # Manual mode never calls the number allocator or creates a registration key.
            payload = {"device_id": requested_id}
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + enrollment_token,
                     "Content-Type": "application/json"},
            method="POST",
        )
        opener = build_opener(NoRedirects())
        for attempt in range(3):
            try:
                with opener.open(request, timeout=30) as response:
                    body = json.loads(response.read(4096))
                break
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise RuntimeError(f"Fleet registration failed (HTTP {error.code})") from None
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise RuntimeError("Fleet registration failed; check connectivity and TLS") from None
            time.sleep(2 ** attempt)
        if (not isinstance(body, dict) or
                not isinstance(body.get("device_id"), str) or
                not isinstance(body.get("device_token"), str) or
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", body["device_id"]) or
                not re.fullmatch(r"[A-Za-z0-9_-]{43}", body["device_token"])):
            raise ValueError("Fleet server returned an invalid device ID or token")
        if requested_id is not None and body["device_id"] != requested_id:
            raise ValueError("Fleet server changed the manually entered device ID")
        return {"device_id": body["device_id"], "device_token": body["device_token"]}


def main() -> int:
    try:
        state_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/etc/sononet/registration.json")
        result = register(os.environ.get("FLEET_ID_API_URL") or os.environ.get("FLEET_API_URL", ""),
                          os.environ.get("FLEET_ENROLLMENT_TOKEN", ""), state_path,
                          requested_id=(os.environ.get("SONONET_DEVICE_ID", "")
                                        if os.environ.get("SONONET_ID_MODE", "manual") == "manual" else None),
                          registration_path=os.environ.get("FLEET_ID_REGISTER_PATH") or DEFAULT_REGISTER_PATH,
                          manual_path=os.environ.get("FLEET_ID_MANUAL_PATH") or DEFAULT_MANUAL_PATH)
        # Strict allowlists above make these safe for both Bash and systemd EnvironmentFile.
        print("SONONET_DEVICE_ID=" + result["device_id"])
        print("DEVICE_TOKEN=" + result["device_token"])
        return 0
    except (ValueError, OSError, RuntimeError):
        # Do not print response bodies, keys, tokens, or attacker-controlled URLs.
        print("Device registration failed. Check the server, enrollment token, and local "
              "registration state; rerun with the same state file.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

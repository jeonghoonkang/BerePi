from __future__ import annotations

import json
import os
import platform
import posixpath
import re
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from urllib.request import HTTPBasicAuthHandler, HTTPSHandler, Request, build_opener
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:  # pragma: no cover - fallback for minimal Python environments
    requests = None  # type: ignore


APP_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = APP_DIR / "settings.json"
STATE_PATH = APP_DIR / "state.json"
REQUEST_TIMEOUT = 60
WEBDAV_NS = {"d": "DAV:"}
RETENTION_MONTHS = 36
DEFAULT_INTERVAL_MINUTES = 30

ALL_SECTIONS = [
    "cpu",
    "network",
    "gpu",
    "disk",
    "user_services",
    "screen",
    "crontab",
    "docker",
]


@dataclass
class WebDAVConfig:
    hostname: str
    root: str
    username: str
    password: str
    verify_ssl: bool = True


class SimpleRequestException(Exception):
    pass


class SimpleResponse:
    def __init__(self, status_code: int, text: str, content: bytes):
        self.status_code = status_code
        self.text = text
        self.content = content

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def raise_for_status(self) -> None:
        if not self.ok:
            raise SimpleRequestException(f"HTTP {self.status_code}: {self.text[:300]}")


class SimpleSession:
    def __init__(self, config: WebDAVConfig):
        auth_handler = HTTPBasicAuthHandler()
        auth_handler.add_password(
            realm=None,
            uri=config.hostname,
            user=config.username,
            passwd=config.password,
        )
        handlers: list[Any] = [auth_handler]
        if not config.verify_ssl:
            import ssl

            handlers.append(HTTPSHandler(context=ssl._create_unverified_context()))
        self.opener = build_opener(*handlers)

    def request(self, method: str, url: str, headers: dict[str, str] | None = None, data: str | bytes | None = None, timeout: int = REQUEST_TIMEOUT) -> SimpleResponse:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        req = Request(url, data=payload, headers=headers or {}, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as response:
                content = response.read()
                text = content.decode("utf-8", errors="replace")
                return SimpleResponse(response.getcode(), text, content)
        except Exception as exc:  # noqa: BLE001
            raise SimpleRequestException(str(exc)) from exc

    def put(self, url: str, data: bytes, headers: dict[str, str] | None = None, timeout: int = REQUEST_TIMEOUT) -> SimpleResponse:
        return self.request("PUT", url, headers=headers, data=data, timeout=timeout)

    def delete(self, url: str, timeout: int = REQUEST_TIMEOUT) -> SimpleResponse:
        return self.request("DELETE", url, timeout=timeout)


REQUEST_ERRORS = (requests.RequestException,) if requests is not None else (SimpleRequestException,)


def default_settings() -> dict[str, Any]:
    return {
        "webdav": {
            "hostname": "",
            "root": "/remote.php/dav/files/username",
            "username": "",
            "password": "",
            "verify_ssl": True,
        },
        "metadata": {
            "ddns_name": "",
            "ssh_port": "22",
            "intro_text": "장비 상태 자동 보고",
        },
        "schedule": {
            "interval_minutes": DEFAULT_INTERVAL_MINUTES,
        },
        "include": {key: True for key in ALL_SECTIONS},
    }


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings() -> dict[str, Any]:
    base = default_settings()
    loaded = load_json_file(SETTINGS_PATH)
    return deep_merge(base, loaded)


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_state() -> dict[str, Any]:
    return load_json_file(STATE_PATH)


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def run_command(command: list[str] | str, timeout: int = 20) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(command, str),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"[command unavailable] {exc}"

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if output:
        return output
    if error:
        return error
    return ""


def as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def normalize_root(root: str) -> str:
    return root.strip("/")


def normalize_remote_path(path: str) -> str:
    return path.strip("/")


def compose_webdav_url(config: WebDAVConfig, remote_path: str = "") -> str:
    host = config.hostname.rstrip("/")
    root = normalize_root(config.root)
    path = normalize_remote_path(remote_path)
    if root and path:
        encoded = "/".join(quote(part) for part in path.split("/") if part)
        return f"{host}/{root}/{encoded}"
    if root:
        return f"{host}/{root}"
    if path:
        encoded = "/".join(quote(part) for part in path.split("/") if part)
        return f"{host}/{encoded}"
    return host


def build_session(config: WebDAVConfig) -> Any:
    if requests is None:
        return SimpleSession(config)  # type: ignore[return-value]
    session = requests.Session()
    session.auth = (config.username, config.password)
    session.verify = config.verify_ssl
    return session


def propfind(session: requests.Session, url: str, depth: str = "1") -> ET.Element:
    response = session.request(
        "PROPFIND",
        url,
        headers={"Depth": depth},
        data=(
            '<?xml version="1.0" encoding="utf-8" ?>'
            '<d:propfind xmlns:d="DAV:"><d:prop>'
            "<d:resourcetype/><d:getlastmodified/><d:creationdate/><d:getcontentlength/>"
            "</d:prop></d:propfind>"
        ),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return ET.fromstring(response.text)


def parse_webdav_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            continue
    return None


def ensure_remote_directories(session: requests.Session, config: WebDAVConfig, remote_dir: str) -> None:
    normalized = normalize_remote_path(remote_dir)
    if not normalized:
        return
    current = ""
    for part in normalized.split("/"):
        current = f"{current}/{part}".strip("/")
        response = session.request("MKCOL", compose_webdav_url(config, current), timeout=REQUEST_TIMEOUT)
        if response.status_code not in {201, 301, 405}:
            response.raise_for_status()


def upload_remote_file(config: WebDAVConfig, remote_path: str, data: bytes, content_type: str = "text/markdown; charset=utf-8") -> None:
    session = build_session(config)
    parent_dir = posixpath.dirname(normalize_remote_path(remote_path))
    ensure_remote_directories(session, config, parent_dir)
    response = session.put(
        compose_webdav_url(config, remote_path),
        data=data,
        headers={"Content-Type": content_type},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


def list_remote_entries(config: WebDAVConfig, remote_dir: str) -> list[dict[str, Any]]:
    session = build_session(config)
    root = propfind(session, compose_webdav_url(config, remote_dir), depth="1")
    expected_prefix = normalize_root(config.root)
    results: list[dict[str, Any]] = []
    current_dir = normalize_remote_path(remote_dir)

    for response_element in root.findall("d:response", WEBDAV_NS):
        href = response_element.findtext("d:href", default="", namespaces=WEBDAV_NS)
        if not href:
            continue
        parsed_href = urlparse(unquote(href)).path.strip("/")
        relative_path = parsed_href[len(expected_prefix):].strip("/") if parsed_href.startswith(expected_prefix) else parsed_href
        if relative_path == current_dir:
            continue

        prop = response_element.find("d:propstat/d:prop", WEBDAV_NS)
        if prop is None:
            continue

        results.append(
            {
                "remote_path": relative_path,
                "name": Path(relative_path).name,
                "is_collection": prop.find("d:resourcetype/d:collection", WEBDAV_NS) is not None,
                "modified_at": parse_webdav_time(prop.findtext("d:getlastmodified", default="", namespaces=WEBDAV_NS)),
                "created_at": parse_webdav_time(prop.findtext("d:creationdate", default="", namespaces=WEBDAV_NS)),
                "size": int(prop.findtext("d:getcontentlength", default="0", namespaces=WEBDAV_NS) or 0),
            }
        )
    return results


def delete_remote_path(config: WebDAVConfig, remote_path: str) -> None:
    session = build_session(config)
    response = session.delete(compose_webdav_url(config, remote_path), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()


def prune_old_remote_files(config: WebDAVConfig, host_dir: str, retention_months: int = RETENTION_MONTHS) -> list[str]:
    cutoff = datetime.now(UTC) - timedelta(days=retention_months * 30)
    deleted: list[str] = []
    try:
        entries = list_remote_entries(config, host_dir)
    except REQUEST_ERRORS:
        return deleted

    for entry in entries:
        if entry["is_collection"]:
            continue
        timestamp = entry["created_at"] or entry["modified_at"] or extract_timestamp_from_name(entry["name"])
        if timestamp is None:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        if timestamp < cutoff:
            try:
                delete_remote_path(config, entry["remote_path"])
                deleted.append(entry["remote_path"])
            except REQUEST_ERRORS:
                continue
    return deleted


def extract_timestamp_from_name(name: str) -> datetime | None:
    match = re.search(r"(\d{8}_\d{6})", name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def hostname() -> str:
    return socket.gethostname()


def boot_marker() -> str:
    for candidate in (Path("/proc/sys/kernel/random/boot_id"), Path("/proc/1/stat")):
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return f"{platform.node()}-{int(time.time())}"


def uptime_minutes() -> int:
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        return max(0, int(uptime_seconds // 60))
    except (OSError, ValueError, IndexError):
        boot_time = time.time() - time.monotonic()
        return max(0, int((time.time() - boot_time) // 60))


def first_after_boot(state: dict[str, Any]) -> bool:
    return state.get("last_boot_marker") != boot_marker()


def parse_public_ip(text: str) -> str:
    text = text.strip()
    match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", text)
    if match:
        return match.group(1)
    ipv6_match = re.search(r"([0-9a-fA-F:]{3,})", text)
    return ipv6_match.group(1) if ipv6_match else text


def get_public_ip() -> str:
    for command in (
        ["curl", "-fsSL", "https://api.ipify.org"],
        ["curl", "-fsSL", "https://checkip.amazonaws.com"],
    ):
        value = run_command(command, timeout=15).strip()
        if value and "unavailable" not in value and "Could not resolve" not in value:
            return parse_public_ip(value)
    return "확인 실패"


def get_ip_route_default() -> tuple[str, str]:
    route_output = run_command(["ip", "route"], timeout=10)
    gateway = "확인 실패"
    internal_ip = "확인 실패"
    for line in route_output.splitlines():
        if not line.startswith("default "):
            continue
        parts = line.split()
        if "via" in parts:
            gateway = parts[parts.index("via") + 1]
        if "src" in parts:
            internal_ip = parts[parts.index("src") + 1]
        break

    if internal_ip == "확인 실패":
        host_output = run_command(["hostname", "-I"], timeout=10).strip()
        if host_output:
            internal_ip = host_output.split()[0]
    return internal_ip, gateway


def read_cpu_times() -> tuple[int, int]:
    values = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
    numbers = [int(value) for value in values]
    idle = numbers[3] + numbers[4]
    total = sum(numbers)
    return idle, total


def cpu_usage_percent() -> float | None:
    try:
        idle1, total1 = read_cpu_times()
        time.sleep(0.2)
        idle2, total2 = read_cpu_times()
    except (OSError, ValueError, IndexError):
        return None
    total_delta = total2 - total1
    idle_delta = idle2 - idle1
    if total_delta <= 0:
        return None
    return round(100.0 * (1.0 - (idle_delta / total_delta)), 1)


def get_cpu_info() -> dict[str, Any]:
    model_name = ""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" not in line:
                continue
            key, value = [part.strip() for part in line.split(":", 1)]
            if key in {"model name", "Hardware"}:
                model_name = value
                break
    except OSError:
        pass

    loadavg = ""
    try:
        loadavg = Path("/proc/loadavg").read_text(encoding="utf-8").split()[:3]
        loadavg = ", ".join(loadavg)
    except OSError:
        loadavg = ""

    return {
        "architecture": platform.machine(),
        "cores": os.cpu_count() or 0,
        "model": model_name or platform.processor() or "unknown",
        "loadavg": loadavg or "확인 실패",
        "usage_percent": cpu_usage_percent(),
    }


def parse_nvidia_smi_lines(output: str) -> list[dict[str, str]]:
    gpus: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append(
            {
                "index": parts[0],
                "name": parts[1],
                "driver": parts[2],
                "memory_total_mb": parts[3],
                "memory_used_mb": parts[4],
                "temperature_c": parts[5],
            }
        )
    return gpus


def get_gpu_info() -> dict[str, Any]:
    smi = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,driver_version,memory.total,memory.used,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        timeout=20,
    )
    if smi and "unavailable" not in smi and "not found" not in smi.lower():
        gpus = parse_nvidia_smi_lines(smi)
        if gpus:
            return {"count": len(gpus), "items": gpus, "source": "nvidia-smi"}

    lspci = run_command("lspci | grep -Ei 'vga|3d|display'", timeout=20)
    if lspci:
        items = [{"name": line.strip()} for line in lspci.splitlines() if line.strip()]
        return {"count": len(items), "items": items, "source": "lspci"}

    return {"count": 0, "items": [], "source": "none"}


def get_disk_usage() -> str:
    return run_command(["df", "-h"], timeout=15) or "확인 실패"


def get_screen_list() -> str:
    return run_command(["screen", "-ls"], timeout=15) or "screen 없음 또는 확인 실패"


def get_crontab_list() -> str:
    username = os.environ.get("USER") or run_command(["whoami"], timeout=5).strip() or "unknown"
    user_cron = run_command(["crontab", "-l"], timeout=15)
    root_hint = run_command(["sudo", "-n", "crontab", "-l"], timeout=15)
    sections = [f"[user:{username}]\n{user_cron or '(empty)'}"]
    if root_hint and "password is required" not in root_hint.lower() and "not allowed" not in root_hint.lower():
        sections.append(f"[root]\n{root_hint}")
    return "\n\n".join(sections)


def get_docker_status() -> str:
    info = run_command(["docker", "info", "--format", "Server {{.ServerVersion}} / {{.OperatingSystem}}"], timeout=20)
    ps = run_command(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], timeout=20)
    if not info and not ps:
        return "docker 없음 또는 권한 부족"
    return f"{info}\n\n{ps}".strip()


def get_user_services() -> str:
    username = os.environ.get("USER") or run_command(["whoami"], timeout=5).strip() or "unknown"
    user_units = run_command(
        ["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend"],
        timeout=20,
    )
    service_files = run_command(
        ["find", str(Path.home() / ".config/systemd/user"), "-maxdepth", "1", "-name", "*.service", "-print"],
        timeout=20,
    )
    launchd = ""
    if platform.system() == "Darwin":
        launchd = run_command(["launchctl", "list"], timeout=20)
    parts = [f"사용자: {username}"]
    if user_units:
        parts.append("[systemd --user running services]\n" + user_units)
    if service_files and "No such file" not in service_files:
        parts.append("[user service files]\n" + service_files)
    if launchd:
        parts.append("[launchctl]\n" + launchd)
    if len(parts) == 1:
        parts.append("확인 가능한 사용자 서비스가 없습니다.")
    return "\n\n".join(parts)


def format_markdown(settings: dict[str, Any], snapshot: dict[str, Any], is_first_boot_message: bool) -> str:
    now = snapshot["collected_at"]
    lines = [
        f"# PulseDAV Report - {snapshot['hostname']}",
        "",
        settings["metadata"].get("intro_text", "").strip() or "장비 상태 자동 보고",
        "",
        f"- 생성 시각: {now}",
        f"- 호스트명: {snapshot['hostname']}",
        f"- 운영체제: {snapshot['os']}",
    ]

    if is_first_boot_message:
        lines.append(f"- 상태 메세지: 부팅한 직후 전송, up 이후 {snapshot['uptime_minutes']}분")
    else:
        lines.append(f"- 상태 메세지: up 이후 {snapshot['uptime_minutes']}분")

    lines.extend(
        [
            f"- 내부 IP: {snapshot['network']['internal_ip']}",
            f"- Public IP: {snapshot['network']['public_ip']}",
            f"- 내부 GW: {snapshot['network']['gateway']}",
            f"- DDNS 이름: {snapshot['network']['ddns_name'] or '미설정'}",
            f"- SSH 포트: {snapshot['network']['ssh_port']}",
            "",
        ]
    )

    include = settings["include"]

    if include.get("cpu"):
        cpu = snapshot["cpu"]
        lines.extend(
            [
                "## CPU 상태",
                "",
                f"- 모델: {cpu['model']}",
                f"- 아키텍처: {cpu['architecture']}",
                f"- 코어 수: {cpu['cores']}",
                f"- Load Average: {cpu['loadavg']}",
                f"- 사용률: {cpu['usage_percent']}%" if cpu["usage_percent"] is not None else "- 사용률: 확인 실패",
                "",
            ]
        )

    if include.get("network"):
        lines.extend(
            [
                "## 네트워크",
                "",
                "```text",
                snapshot["network"]["detail"],
                "```",
                "",
            ]
        )

    if include.get("gpu"):
        gpu = snapshot["gpu"]
        lines.extend([f"## GPU 리스트 및 스펙", "", f"- GPU 개수: {gpu['count']}", f"- 수집 소스: {gpu['source']}", ""])
        if gpu["items"]:
            lines.append("```text")
            for item in gpu["items"]:
                lines.append(", ".join(f"{key}={value}" for key, value in item.items()))
            lines.append("```")
        else:
            lines.append("GPU 없음")
        lines.append("")

    if include.get("disk"):
        lines.extend(["## HDD 공간", "", "```text", snapshot["disk"], "```", ""])

    if include.get("user_services"):
        lines.extend(["## 서비스 중 사용자가 실행한 서비스", "", "```text", snapshot["user_services"], "```", ""])

    if include.get("screen"):
        lines.extend(["## screen 리스트", "", "```text", snapshot["screen"], "```", ""])

    if include.get("crontab"):
        lines.extend(["## crontab", "", "```text", snapshot["crontab"], "```", ""])

    if include.get("docker"):
        lines.extend(["## docker 운영 상태", "", "```text", snapshot["docker"], "```", ""])

    return "\n".join(lines).rstrip() + "\n"


def collect_snapshot(settings: dict[str, Any]) -> dict[str, Any]:
    internal_ip, gateway = get_ip_route_default()
    return {
        "hostname": hostname(),
        "os": f"{platform.system()} {platform.release()}",
        "collected_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "uptime_minutes": uptime_minutes(),
        "cpu": get_cpu_info(),
        "network": {
            "internal_ip": internal_ip,
            "public_ip": get_public_ip(),
            "gateway": gateway,
            "ddns_name": settings["metadata"].get("ddns_name", "").strip(),
            "ssh_port": str(settings["metadata"].get("ssh_port", "22")).strip() or "22",
            "detail": run_command(["ip", "addr"], timeout=15) or run_command(["ifconfig"], timeout=15) or "확인 실패",
        },
        "gpu": get_gpu_info(),
        "disk": get_disk_usage(),
        "user_services": get_user_services(),
        "screen": get_screen_list(),
        "crontab": get_crontab_list(),
        "docker": get_docker_status(),
    }


def validate_settings(settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    webdav = settings.get("webdav", {})
    if not str(webdav.get("hostname", "")).strip():
        errors.append("WebDAV 주소가 비어 있습니다.")
    if not str(webdav.get("username", "")).strip():
        errors.append("WebDAV 사용자명이 비어 있습니다.")
    if not str(webdav.get("password", "")).strip():
        errors.append("WebDAV 비밀번호가 비어 있습니다.")
    interval = int(settings.get("schedule", {}).get("interval_minutes", DEFAULT_INTERVAL_MINUTES) or DEFAULT_INTERVAL_MINUTES)
    if interval <= 0:
        errors.append("전송 주기는 1분 이상이어야 합니다.")
    return errors


def build_webdav_config(settings: dict[str, Any]) -> WebDAVConfig:
    webdav = settings["webdav"]
    return WebDAVConfig(
        hostname=str(webdav.get("hostname", "")).strip(),
        root=str(webdav.get("root", "")).strip(),
        username=str(webdav.get("username", "")).strip(),
        password=str(webdav.get("password", "")).strip(),
        verify_ssl=as_bool(webdav.get("verify_ssl"), True),
    )


def send_once(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    errors = validate_settings(settings)
    if errors:
        raise ValueError(" / ".join(errors))

    state = load_state()
    current_boot_marker = boot_marker()
    first_boot = state.get("last_boot_marker") != current_boot_marker
    snapshot = collect_snapshot(settings)
    markdown = format_markdown(settings, snapshot, first_boot)

    host_dir = posixpath.join("pulsedav", normalize_remote_path(hostname())).strip("/")
    file_name = f"pulse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    remote_path = posixpath.join(host_dir, file_name).strip("/")
    webdav_config = build_webdav_config(settings)
    upload_remote_file(webdav_config, remote_path, markdown.encode("utf-8"))
    deleted = prune_old_remote_files(webdav_config, host_dir, RETENTION_MONTHS)

    new_state = {
        "last_boot_marker": current_boot_marker,
        "last_sent_at": datetime.now().astimezone().isoformat(),
        "last_remote_path": remote_path,
        "last_uptime_minutes": snapshot["uptime_minutes"],
    }
    save_state(new_state)

    return {
        "remote_path": remote_path,
        "deleted_paths": deleted,
        "first_boot_message": first_boot,
        "uptime_minutes": snapshot["uptime_minutes"],
        "preview": markdown,
    }


def run_loop(interval_minutes: int | None = None) -> None:
    settings = load_settings()
    minutes = interval_minutes or int(settings["schedule"].get("interval_minutes", DEFAULT_INTERVAL_MINUTES))
    while True:
        try:
            send_once(settings)
        except Exception as exc:
            print(f"[pulsedav] send failed: {exc}")
        time.sleep(max(1, minutes) * 60)


def quoted_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)

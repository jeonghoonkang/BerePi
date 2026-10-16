#!/usr/bin/env python3
"""External llm_routing monitor. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class CheckError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward credentials to redirected sites.


def request_json(url, timeout, password="", payload=None):
    headers = {"Accept": "application/json"}
    if password:
        headers["Authorization"] = "Bearer " + password
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise CheckError("응답 크기 제한 초과")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise CheckError("JSON 객체가 아닌 응답")
        return result
    except urllib.error.HTTPError as exc:
        raise CheckError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CheckError("연결 실패 / DNS·TLS·네트워크 오류 또는 시간 초과") from None
    except (ValueError, UnicodeError):
        raise CheckError("잘못된 JSON 응답") from None


def inspect_status(data, now, max_age):
    """Require authenticated metrics; never infer health from HTTP 200 alone."""
    targets, metrics = data.get("targets"), data.get("metrics")
    if not isinstance(targets, list) or not isinstance(metrics, dict):
        return {"routing:auth": "상세 상태 조회 실패: 라우팅 비밀번호 또는 API 응답 형식을 확인하세요."}
    issues = {}
    enabled = 0
    seen = set()
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get("id"), str):
            issues["routing:schema"] = "잘못된 target 형식"
            continue
        if not target.get("enabled", True):
            continue
        enabled += 1
        target_id = target["id"]
        if target_id in seen:
            issues["routing:duplicate"] = "중복 target ID"
        seen.add(target_id)
        label = f"{target.get('name', target_id)} | 모델={target.get('model', '-')} | 서버={target.get('host', '-')}:{target.get('port', '-')}"
        metric = metrics.get(target_id)
        reasons = []
        if not isinstance(metric, dict):
            reasons.append("상태 정보 없음")
        else:
            if metric.get("status") != "ok":
                reasons.append("상태 오류 또는 확인되지 않음")
            available = metric.get("available_targets")
            if isinstance(available, (int, float)) and available <= 0:
                reasons.append("사용 가능한 모델/대상 없음")
            stamp = metric.get("last_health_probe_at")
            if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or stamp <= 0 or now - stamp > max_age or stamp > now + 60:
                reasons.append("상태 점검 정보가 없거나 오래됨/시간 불일치")
        if reasons:
            issues["target:" + target_id] = label + " — " + ", ".join(reasons)
    if not enabled:
        issues["routing:empty"] = "활성화된 라우팅 대상이 없습니다."
    return issues


def collect(config):
    base = config["url"].rstrip("/")
    try:
        health = request_json(base + "/health", config["timeout_seconds"])
        if health.get("ok") is not True:
            raise CheckError("/health가 정상 상태를 반환하지 않음")
        status = request_json(base + "/api/status", config["timeout_seconds"], config["password"])
        return inspect_status(status, time.time(), config["max_status_age_seconds"])
    except CheckError as exc:
        return {"routing:connection": "라우팅 서비스 점검 실패: " + str(exc)}


def send_telegram(config, message):
    # Never include server-provided error bodies or token-bearing URLs in logs.
    for secret in (config["bot_token"], config["password"]):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    for start in range(0, len(message), 1800):
        result = request_json(
            "https://api.telegram.org/bot" + config["bot_token"] + "/sendMessage",
            20, payload={"chat_id": config["chat_id"], "text": message[start:start + 1800]},
        )
        if result.get("ok") is not True:
            raise CheckError("Telegram 전송 거부: 토큰과 chat_id를 확인하세요.")


def update_state(state, issues, config, now, send):
    """Only acknowledge a notification after all message chunks are delivered."""
    previous = state.get("active", {})
    if any(key in issues for key in ("routing:connection", "routing:auth", "routing:schema")):
        # An unreachable router cannot establish recovery of its backends.
        issues = {**previous, **issues}
    counts = state.setdefault("counts", {})
    counts = {key: counts.get(key, 0) + 1 for key in issues}
    state["counts"] = counts
    active = {key: value for key, value in issues.items()
              if key in previous or counts[key] >= config["failure_threshold"]}
    recovered = {key: value for key, value in previous.items() if key not in issues}
    changed = active != previous
    reminder = bool(active) and now - state.get("last_sent", 0) >= config["reminder_seconds"]
    startup = not state.get("initialized") and not issues
    if changed or reminder or startup:
        lines = ["[LLM HTTP Heartbeat] " + config["name"], time.strftime("%Y-%m-%d %H:%M:%S %z")]
        if active:
            lines += ["장애 감지:", *active.values()]
        if recovered:
            lines += ["복구/해제 (대상 비활성화·삭제 포함):", *recovered.values()]
        if startup:
            lines += ["감시 시작: 라우팅 서비스 및 활성 대상 상태 정상"]
        send("\n".join(lines))
        state.update(active=active, last_sent=now, initialized=True)
    return state


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    for key, env in (("bot_token", "TELEGRAM_BOT_TOKEN"), ("chat_id", "TELEGRAM_CHAT_ID"),
                     ("password", "LLM_ROUTING_PASSWORD"), ("url", "LLM_ROUTING_URL")):
        config[key] = os.environ.get(env, str(config.get(key, ""))).strip()
        if not config[key]:
            raise ValueError(f"{key} 또는 {env} 설정이 필요합니다.")
    parsed = urllib.parse.urlsplit(config["url"])
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("url에는 인증정보/쿼리 없는 HTTP(S) 주소를 입력하세요.")
    config.setdefault("name", "llm_routing")
    for key, default in (("interval_seconds", 60), ("timeout_seconds", 120),
                         ("max_status_age_seconds", 300), ("failure_threshold", 2),
                         ("reminder_seconds", 3600)):
        value = config.setdefault(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key}는 양수여야 합니다.")
    if not isinstance(config["failure_threshold"], int):
        raise ValueError("failure_threshold는 정수여야 합니다.")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--once", action="store_true", help="한 번 점검 후 종료")
    parser.add_argument("--dry-run", action="store_true", help="전송/상태 저장 없이 한 번 점검")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        state_path = args.config.resolve().parent / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() and not args.dry_run else {}
        if not isinstance(state, dict) or not isinstance(state.get("active", {}), dict) or not isinstance(state.get("counts", {}), dict):
            raise ValueError("state.json 형식 오류")
        while True:
            issues = collect(config)
            print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False), flush=True)
            if args.dry_run:
                return int(bool(issues))
            failed_send = False
            try:
                update_state(state, issues, config, time.time(), lambda text: send_telegram(config, text))
            except CheckError as exc:
                print(f"알림 전송 실패 (다음 점검에서 재시도): {exc}", file=sys.stderr, flush=True)
                failed_send = True
            temporary = state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            temporary.replace(state_path)
            if args.once:
                return 2 if failed_send else int(bool(issues))
            time.sleep(config["interval_seconds"])
    except (OSError, ValueError, TypeError) as exc:
        print(f"설정/상태 파일 오류: {type(exc).__name__}. 설정 및 파일 권한을 확인하세요.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

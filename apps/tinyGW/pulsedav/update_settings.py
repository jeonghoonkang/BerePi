#!/usr/bin/env python3
"""Rebuild a personal configuration using the current settings template."""

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile


APP_DIR = Path(__file__).resolve().parent


def merge_settings(template, existing, path=()):
    """Use template keys/order and retain compatible existing values."""
    if isinstance(template, dict):
        if not isinstance(existing, dict):
            raise ValueError(f"자료형이 변경된 항목을 확인하세요: {'.'.join(path)}")
        return {
            key: merge_settings(value, existing[key], path + (key,))
            if key in existing else copy.deepcopy(value)
            for key, value in template.items()
        }
    # PulseDAV explicitly supports either a string or a list for webdav.sub.
    if path == ("webdav", "sub") and isinstance(existing, list):
        if all(isinstance(item, str) for item in existing):
            return copy.deepcopy(existing)
    if type(template) is not type(existing):
        raise ValueError(f"자료형이 변경된 항목을 확인하세요: {'.'.join(path)}")
    return copy.deepcopy(existing)


def read_settings(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"잘못된 JSON: {path} (줄 {exc.lineno}, 열 {exc.colno})") from None
    if not isinstance(value, dict):
        raise ValueError(f"JSON 최상위는 객체여야 합니다: {path}")
    return value


def rebuild(template_path, target_path):
    template_path = template_path.resolve()
    target_path = target_path.resolve()
    if template_path == target_path or (
        target_path.exists() and os.path.samefile(template_path, target_path)
    ):
        raise ValueError("템플릿과 출력 파일은 서로 달라야 합니다.")
    template = read_settings(template_path)
    exists = target_path.exists()
    existing = read_settings(target_path) if exists else {}
    merged = merge_settings(template, existing)
    # Do not silently discard credentials when a template renames/removes them.
    for section, keys in {"webdav": ("username", "password"),
                          "iptime": ("user_id", "user_pw")}.items():
        previous = existing.get(section, {})
        current = merged.get(section, {})
        if isinstance(previous, dict):
            for key in keys:
                if key in previous and (
                    not isinstance(current, dict) or key not in current
                ):
                    raise ValueError(f"인증 항목이 삭제/이동되었습니다. 직접 매핑하세요: {section}.{key}")
    payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    backup = None
    if exists:
        fd, name = tempfile.mkstemp(prefix=target_path.name + ".bak.", dir=target_path.parent)
        backup = Path(name)
        with os.fdopen(fd, "wb") as output:
            output.write(target_path.read_bytes())
    fd, name = tempfile.mkstemp(prefix="." + target_path.name + ".", dir=target_path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target_path)
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description="최신 템플릿 구조에 맞춰 기존 개인 설정을 보존하여 재생성합니다.")
    parser.add_argument("--template", type=Path, default=APP_DIR / "settings.json")
    parser.add_argument("--config", type=Path, default=APP_DIR / "this_settings.json")
    args = parser.parse_args()
    try:
        backup = rebuild(args.template, args.config)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"설정 재생성 실패: {exc}\n")
    print(f"설정 생성 완료: {args.config}")
    if backup:
        print(f"기존 파일 백업: {backup}")


if __name__ == "__main__":
    main()

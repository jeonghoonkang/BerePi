"""Summarize public or authenticated routing status using Python 3.6+ stdlib."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone


TARGET_FIELDS = (
    "id", "name", "host", "port", "model", "api_type", "enabled",
    "selected_gpu", "selected_gpu_label", "gpu_info", "gpu_type", "proxy_port",
)
METRIC_FIELDS = (
    "status", "available_targets", "dispatch_eligible", "uptime", "queue_state",
    "active_requests", "pending_queue", "queue_max_per_target", "total_prompts",
    "average_response_seconds", "last_response_seconds", "last_seen_at",
    "last_health_probe_at", "gpu_info", "gpu_type", "selected_gpu_device", "last_error",
)


def summarize(payload):
    """Count registered targets, distinct models, and explicitly selected GPU IDs."""
    if not isinstance(payload, dict) or not isinstance(payload.get("targets"), list):
        raise ValueError("Expected /api/status JSON containing a targets list")
    metrics = payload.get("metrics")
    detailed = isinstance(metrics, dict)
    metrics = metrics if detailed else {}
    targets, gpus, models, unknown_gpu = [], {}, {}, []
    for source in payload["targets"]:
        if not isinstance(source, dict):
            raise ValueError("Invalid target entry")
        target = {key: source[key] for key in TARGET_FIELDS if key in source}
        metric = metrics.get(source.get("id"), {})
        metric = metric if isinstance(metric, dict) else {}
        target["metrics"] = {key: metric[key] for key in METRIC_FIELDS if key in metric}
        enabled = source.get("enabled", True) is True
        eligible = metric.get("dispatch_eligible", source.get("dispatch_eligible"))
        available = metric.get("available_targets", source.get("available_targets"))
        if not isinstance(eligible, bool):
            eligible = available > 0 if isinstance(available, (int, float)) else None
        target["enabled"] = enabled
        target["dispatch_eligible"] = eligible if enabled else False
        target["available_targets"] = available
        targets.append(target)
        if target["dispatch_eligible"] is not True:
            continue
        model = str(source.get("model") or "(unspecified)")
        models.setdefault(model, []).append(source.get("id"))
        _collect_gpus(source, gpus, unknown_gpu)
    return {
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "detail_available": detailed,
        "uptime": payload.get("uptime"),
        "registered_targets": len(targets),
        "enabled_targets": sum(item["enabled"] for item in targets),
        "dispatchable_targets": sum(item["dispatch_eligible"] is True for item in targets),
        "unknown_availability_targets": sum(item["dispatch_eligible"] is None for item in targets),
        "available_unique_models": len(models),
        "models": models,
        "known_selected_gpu_count": len(gpus),
        "gpus": list(gpus.values()),
        "unresolved_gpu_targets": unknown_gpu,
        "targets": targets,
        "notes": [
            "Available means dispatch_eligible=true, not necessarily idle; status may be cached.",
            "Models are registered routing model names, not all models installed on each backend.",
            "GPU count covers explicit numeric IDs/UUIDs on dispatchable targets, deduplicated by host + ID.",
            "auto/all/unspecified are unresolved. CPU/cloud targets are not counted as GPUs.",
            "Host aliases may identify the same machine; physical GPU inventory is not exposed by this API.",
        ],
    }


def _collect_gpus(target, gpus, unknown):
    selected = str(target.get("selected_gpu") or "").strip()
    if selected.lower() in {"cpu", "none"} or target.get("api_type") in {"bedrock", "google_ai_studio"}:
        return
    ids = [item.strip() for item in selected.split(",")]
    if not all(re.fullmatch(r"(?:\d+|GPU-[A-Za-z0-9-]+|MIG-[A-Za-z0-9/-]+)", item) for item in ids):
        unknown.append(target.get("id"))
        return
    host = str(target.get("host") or "").strip().lower()
    if not host:
        unknown.append(target.get("id"))
        return
    for gpu in set(ids):
        gpu = str(int(gpu)) if gpu.isdigit() else gpu
        entry = gpus.setdefault((host, gpu), {"host": host, "gpu_id": gpu, "target_ids": [], "models": []})
        entry["target_ids"].append(target.get("id"))
        model = target.get("model")
        if model not in entry["models"]:
            entry["models"].append(model)


def render(report):
    """Render a readable summary followed by per-target details."""
    lines = [
        "LLM Routing 모델 / GPU 상태", "조회 시각: " + report["queried_at"],
        "라우터 uptime: " + str(report["uptime"] or "미제공"),
        "등록 대상: {registered_targets} / 활성: {enabled_targets} / 배정 가능: {dispatchable_targets}"
        " / 상태 미확인: {unknown_availability_targets}".format(**report),
        "사용 가능 고유 모델: {}개".format(report["available_unique_models"]),
        "명시적으로 선택된 GPU: {}개 / GPU 수 미확인 대상: {}개".format(
            report["known_selected_gpu_count"], len(report["unresolved_gpu_targets"])),
        "\n[사용 가능한 모델]",
    ]
    lines.extend("- {}: {}".format(model, ", ".join(map(str, ids))) for model, ids in report["models"].items())
    if not report["models"]:
        lines.append("- 없음 (미확인 상태는 사용 가능으로 집계하지 않음)")
    lines.append("\n[명시적으로 선택된 GPU 목록]")
    for gpu in report["gpus"]:
        lines.append("- {host} GPU {gpu_id}: {models} / 대상 {target_ids}".format(**gpu))
    if not report["gpus"]:
        lines.append("- 확인 가능한 명시적 GPU 없음 (물리 GPU가 0개라는 의미는 아님)")
    if report["unresolved_gpu_targets"]:
        lines.append("- GPU 수 미확인 대상: " + ", ".join(map(str, report["unresolved_gpu_targets"])))
    lines.append("\n[대상별 상세]")
    for target in report["targets"]:
        lines.append(json.dumps(target, ensure_ascii=False, indent=2))
    if not report["detail_available"]:
        lines.append("\n공개 응답: 상세 큐/GPU 상태가 필요하면 LLM_ROUTING_PASSWORD를 설정하세요.")
    lines.extend(["\n[집계 기준]"] + ["- " + note for note in report["notes"]])
    return "\n".join(lines)


def main():
    """Read the curl response from stdin and print a report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = summarize(json.load(sys.stdin))
    except (ValueError, TypeError) as exc:
        print("상태 응답 처리 실패: {}".format(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

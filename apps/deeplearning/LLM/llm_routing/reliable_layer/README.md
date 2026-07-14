# Reliable Layer

`server_routing.py`의 `route_prompt(handler, payload)`를 감싸는 표준 라이브러리 기반 계층입니다.

## 기능

- 원본 prompt 보존 및 내부 제어 필드의 backend 전달 차단
- `remember: true`인 경우에만 사용자별 SQLite 기억 저장
- 기억을 명확한 경계로 prompt/messages에 추가
- timeout, 연결 오류, HTTP 408/425/429/5xx 재시도
- exponential backoff + jitter, 전체 deadline, 최대 시도 횟수
- `preparing`, `dispatching`, `retrying`, `completed`, `failed` 이벤트

## 기존 서버 연결

```python
from reliable_layer.adapter import route_reliably

if payload.get("reliable") is True:
    result = route_reliably(self, payload, route_prompt, app_dir=APP_DIR)
else:
    result = route_prompt(self, payload)
self.write_json(result)
```

동기 JSON API는 중간 HTTP 메시지를 전달할 수 없습니다. `ProgressEvent`를 SSE, WebSocket,
job-event API 또는 로그 callback에 연결해야 호출자가 실시간 진행 상태를 받을 수 있습니다.

## 요청 예시

```json
{"user_id":"user-123","prompt":"한국어로 답해주세요","reliable":true,"remember":true,
 "memory_content":"한국어 답변 선호","use_memory":true}
```

자연어에서 기억 의사를 추측하지 않습니다. API 호출자가 `remember: true`로 사용자 동의를 전달해야 합니다.

## 환경 변수

`LLM_RELIABLE_MAX_ATTEMPTS`, `LLM_RELIABLE_BASE_BACKOFF`, `LLM_RELIABLE_MAX_BACKOFF`,
`LLM_RELIABLE_TOTAL_DEADLINE`, `LLM_RELIABLE_MEMORY_ENABLED`, `LLM_RELIABLE_MAX_MEMORIES`,
`LLM_RELIABLE_MAX_MEMORY_CHARS`, `LLM_RELIABLE_RETRY_MESSAGE`를 지원합니다.

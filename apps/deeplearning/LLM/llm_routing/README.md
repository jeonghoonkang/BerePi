# LLM Routing

외부에서 들어오는 prompt 요청을 여러 LLM 서버 중 하나로 전달하고, 받은 결과를 요청한 클라이언트로 되돌려주는 라우팅 서버입니다.

## 기능

- 웹 UI에서 LLM 리스트 관리: IP 주소, PORT, 모델 이름, GPU 정보, GPU 종류, 접근 ID, PASS
- 각 LLM 상태 표시: GPU 정보, uptime, 처리 prompt 수, queue 상태, pending queue 수, 평균 응답시간
- 서비스 탭: 접속한 prompt 클라이언트 수, 클라이언트별 요청 prompt 수, 초당 질의 수
- 로컬머신 탭: 현재 시스템 CPU 상태, GPU 상태, 접근 로그
- API 라우팅: `POST /api/generate` 요청을 Ollama, OpenAI API, vLLM OpenAI 호환 서버로 전달

## 실행

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/llm_routing
chmod +x run.sh start.sh stop.sh
./run.sh
```

백그라운드 실행:

```bash
./start.sh
./stop.sh
```

기본 포트는 `4004`입니다.

```bash
LLM_ROUTING_PORT=4005 ./run.sh
```

웹 UI:

```text
http://SERVER_IP:4004
```

처음 접속하면 password 입력 화면이 표시됩니다. 기본 password 파일은 `admin_password.conf`이며, 파일이 없으면 첫 실행 시 `change-me-now` 값으로 생성됩니다. 운영 전에 이 파일 내용을 원하는 password로 변경하거나 환경 변수로 지정하세요.

```bash
echo 'my-secret-password' > admin_password.conf
chmod 600 admin_password.conf
```

환경 변수로 지정할 수도 있습니다.

```bash
LLM_ROUTING_ADMIN_PASSWORD='my-secret-password' ./run.sh
```

## Prompt API

자동 대상 선택:

```bash
curl -X POST http://127.0.0.1:4004/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"client-a","prompt":"hello"}'
```

특정 LLM 대상 지정:

```bash
curl -X POST http://127.0.0.1:4004/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"client-a","target_id":"TARGET_ID","prompt":"hello"}'
```

응답 예:

```json
{
  "ok": true,
  "target_id": "TARGET_ID",
  "target_name": "Local Ollama",
  "model": "llama3.1",
  "response_seconds": 1.23,
  "response": "...",
  "raw": {}
}
```

## 설정 파일

LLM 대상 목록은 `llm_targets.json`에 저장됩니다. 처음 실행하면 샘플 대상이 비활성 상태로 생성됩니다.

```json
{
  "targets": [
    {
      "id": "local-ollama",
      "name": "Local Ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "model": "llama3.1",
      "api_type": "ollama",
      "gpu_info": "RTX 5090",
      "gpu_type": "NVIDIA",
      "access_id": "",
      "password": "",
      "enabled": true
    }
  ]
}
```

`api_type`은 `ollama`, `openai`, `vllm`을 지원합니다.

## Backend Type

- `ollama`: `http://HOST:PORT/api/generate`와 `http://HOST:PORT/api/tags`를 사용합니다. `/api/tags`가 없는 Gemma4OllamaServer 형태는 `/health`의 `models`, GPU, queue 정보를 fallback으로 사용합니다.
- `openai`: `http://HOST:PORT/v1/chat/completions`와 `http://HOST:PORT/v1/models`를 사용합니다.
- `vllm`: vLLM의 OpenAI 호환 서버 기준으로 `http://HOST:PORT/v1/chat/completions`, `http://HOST:PORT/v1/models`, `http://HOST:PORT/health`, `http://HOST:PORT/metrics`를 사용합니다.

OpenAI/vLLM 타입의 상태 확인은 `tospark_client`와 같은 probe 방식을 사용합니다. `/health`, `/v1/models`, `/metrics`를 확인하고, vLLM의 `vllm:num_requests_running`, `vllm:num_requests_waiting` metric이 있으면 active/pending queue 상태에 반영합니다.

OpenAI/vLLM 타입에서 `password` 또는 `access_id` 값이 있으면 `Authorization: Bearer ...` 헤더로 전달합니다. Ollama 타입에서 `access_id` 값이 있으면 Basic Auth로 전달합니다. `keti-ev1.iptime.org:8082`처럼 `/api/generate`가 401을 반환하는 서버는 대상 설정에 접근 ID와 PASS를 입력해야 합니다.

vLLM 예:

```json
{
  "targets": [
    {
      "id": "vllm-gpu-1",
      "name": "vLLM GPU 1",
      "host": "192.168.0.10",
      "port": 8000,
      "model": "Qwen/Qwen2.5-32B-Instruct",
      "api_type": "vllm",
      "gpu_info": "4x RTX 5090",
      "gpu_type": "NVIDIA",
      "access_id": "",
      "password": "",
      "enabled": true
    }
  ]
}
```

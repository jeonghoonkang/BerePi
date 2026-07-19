# LLM Routing

외부에서 들어오는 prompt 요청을 여러 LLM 서버 중 하나로 전달하고, 받은 결과를 요청한 클라이언트로 되돌려주는 라우팅 서버입니다.

## 기능

- 웹 UI에서 LLM 리스트 관리: IP 주소, PORT, 모델 이름, GPU 정보, GPU 종류, 접근 ID, PASS
- 각 LLM 상태 표시: GPU 정보, uptime, 처리 prompt 수, queue 상태, pending queue 수, 평균 응답시간
- 서비스 탭: 접속한 prompt 클라이언트 수, 클라이언트별 요청 prompt 수, 초당 질의 수
- 로컬머신 탭: 현재 시스템 CPU 상태, GPU 상태, 접근 로그
- 프롬프트 테스트 탭: 단일 대상 테스트와 활성화된 전체 LLM 대상의 동일 prompt 응답/소요 시간 비교
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

프롬프트 테스트 탭에서 `전송`은 선택한 대상 또는 자동 선택 대상으로 prompt를 1회 보냅니다. `전체 모델 비교`는 활성화된 모든 LLM 대상 queue에 동일 prompt를 한 번에 넣고, 각 모델별 수신 내용과 소요 시간을 표로 비교합니다. 비교 결과의 GPU 칸에는 저장된 `selected_gpu_label`이 있으면 선택된 system device label을 우선 표시합니다.

## 관리 화면 접근 Password 적용 방법

처음 LLM Routing 페이지에 접속하면 password 입력 화면이 표시됩니다. 관리 화면 password는 `admin_password.conf` 파일 또는 `LLM_ROUTING_ADMIN_PASSWORD` 환경 변수로 적용할 수 있습니다.

### 1. password 파일로 적용

`llm_routing` 디렉터리에서 원하는 password를 `admin_password.conf`에 저장합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/llm_routing
echo 'my-secret-password' > admin_password.conf
chmod 600 admin_password.conf
```

서비스를 재시작합니다.

```bash
./stop.sh
./start.sh
```

이후 브라우저에서 `http://SERVER_IP:4004`에 접속하고, 위에서 저장한 `my-secret-password`를 입력합니다.

`admin_password.conf` 파일이 없으면 서버 첫 실행 시 기본값 `change-me-now`로 자동 생성됩니다. 운영 전에 반드시 원하는 password로 변경하세요.

### 2. 환경 변수로 임시 적용

파일을 변경하지 않고 실행할 때만 password를 지정할 수도 있습니다.

```bash
LLM_ROUTING_ADMIN_PASSWORD='my-secret-password' ./run.sh
```

백그라운드 실행에 적용하려면 다음처럼 실행합니다.

```bash
LLM_ROUTING_ADMIN_PASSWORD='my-secret-password' ./start.sh
```

환경 변수 값이 있으면 `admin_password.conf`보다 우선 적용됩니다.

## Prompt API

외부 머신에서는 LLM Routing 서버의 `4004` 포트로 prompt를 전송합니다. prompt 클라이언트용 API도 관리 화면과 같은 password가 필요합니다. 외부 클라이언트는 `Authorization: Bearer <password>` 또는 `X-LLM-Routing-Password: <password>` 헤더를 보내야 합니다.

지원 endpoint:

- `POST /api/generate`: 기본 LLM Routing generate API
- `POST /generate`: `/api/generate`와 동일한 alias
- `POST /api/chat`: chat 클라이언트용 alias
- `POST /v1/chat/completions`: OpenAI 호환 chat completions API
- `POST /api/generate/stream`: `dispatch_info`를 먼저 보내는 SSE API

기존 prompt endpoint에 `"stream": true`를 보내도 SSE로 응답합니다. 첫 이벤트는 라우팅
대상을 확정한 `dispatch_info`, 두 번째 이벤트는 LLM의 `response`, 마지막 이벤트는
`done`입니다. 실패한 경우 `response` 대신 `error` 이벤트를 보냅니다.

```bash
curl -N -X POST http://127.0.0.1:4004/api/generate/stream \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{"client_id":"client-a","prompt":"hello"}'
```

```text
event: dispatch_info
data: {"dispatch_info":{"status":"selected","model_number":1,"target":{...}}}

event: response
data: {"ok":true,"response":"...",...}

event: done
data: {"ok":true}
```

자동 대상 선택:

```bash
curl -X POST http://127.0.0.1:4004/api/generate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{"client_id":"client-a","prompt":"hello"}'
```

`/generate` alias:

```bash
curl -X POST http://127.0.0.1:4004/generate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{"client_id":"client-a","prompt":"hello"}'
```

특정 LLM 대상 지정:

```bash
curl -X POST http://127.0.0.1:4004/api/generate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{"client_id":"client-a","target_id":"TARGET_ID","prompt":"hello"}'
```

다른 머신에서 호출할 때는 `127.0.0.1` 대신 LLM Routing 서버 IP 또는 DNS 이름을 사용합니다.

```bash
curl -X POST http://LLM_ROUTING_SERVER_IP:4004/api/generate \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{
    "client_id": "my-client-01",
    "prompt": "GPU 서버 상태를 한 문장으로 요약해줘",
    "timeout": 180
  }'
```

Python 예제:

```python
import requests

url = "http://LLM_ROUTING_SERVER_IP:4004/api/generate"
payload = {
    "client_id": "python-client-01",
    "prompt": "오늘 처리할 작업 우선순위를 정리해줘",
    # "target_id": "TARGET_ID",  # 특정 LLM으로 보낼 때만 사용
    "timeout": 180,
}

response = requests.post(
    url,
    json=payload,
    headers={"Authorization": "Bearer my-secret-password"},
    timeout=200,
)
response.raise_for_status()
data = response.json()

print("dispatch:", data.get("dispatch_info"))
print("target:", data.get("target_name"))
print("model:", data.get("model"))
print("seconds:", data.get("response_seconds"))
print("answer:", data.get("response"))
```

라우팅 대상은 요청을 받은 직후 결정되며, 첫 JSON 응답의 `dispatch_info`에 선택 상태,
활성 모델 번호와 대상 상세 정보가 포함됩니다. 기존 `llm_dispatch_model_number` 및
`llm_dispatch_target` 필드도 호환성을 위해 함께 제공됩니다.

JavaScript fetch 예제:

```javascript
const response = await fetch("http://LLM_ROUTING_SERVER_IP:4004/api/generate", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer my-secret-password"
  },
  body: JSON.stringify({
    client_id: "web-client-01",
    prompt: "이 문장을 영어로 번역해줘: 안녕하세요",
    timeout: 180
  })
});

if (!response.ok) {
  throw new Error(await response.text());
}

const data = await response.json();
console.log(data.response);
```

OpenAI 호환 API 예제:

```bash
curl -X POST http://LLM_ROUTING_SERVER_IP:4004/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer my-secret-password' \
  -d '{
    "model": "auto",
    "messages": [
      {"role": "user", "content": "LLM Routing 상태를 짧게 요약해줘"}
    ],
    "temperature": 0.2
  }'
```

OpenAI 호환 응답의 `routing` 필드에는 실제 사용된 target, IP/PORT, GPU 정보가 포함됩니다.

요청 필드:

- `prompt`: 전송할 prompt 문자열
- `client_id`: 호출한 외부 클라이언트 이름 또는 ID
- `target_id`: 특정 LLM 대상에 보낼 때 사용합니다. 생략하면 자동 선택합니다.
- `timeout`: backend LLM 응답 대기 시간입니다. 초 단위입니다.

현재 `/api/generate`는 활성화된 LLM target마다 별도 queue와 worker를 사용합니다. target은 등록된 모델/GPU 조합으로 취급되며, 각 target queue는 기본 최대 10개 prompt를 보관합니다. 자동 선택 요청은 idle target을 우선 선택하고, 모든 target이 처리 중이면 queue 여유가 있으며 pending/active 부하가 가장 낮은 target으로 들어갑니다. target worker가 queue에서 prompt를 하나씩 꺼내 backend LLM으로 전송합니다.

HTTP 응답은 queue에 넣은 뒤 해당 prompt 처리가 완료될 때까지 기다렸다가 반환합니다. 모든 target queue가 가득 차면 `429 Too Many Requests`를 반환합니다. target별 queue 최대 길이는 `LLM_ROUTING_QUEUE_MAX_PER_TARGET` 환경 변수로 변경할 수 있습니다.

응답 예:

```json
{
  "ok": true,
  "target_id": "TARGET_ID",
  "target_name": "Local Ollama",
  "target_host": "127.0.0.1",
  "target_port": 11434,
  "target_url": "http://127.0.0.1:11434",
  "api_type": "ollama",
  "model": "llama3.1",
  "gpu_type": "NVIDIA",
  "gpu_info": "RTX 5090",
  "selected_gpu": "0",
  "response_seconds": 1.23,
  "response": "...",
  "raw": {}
}
```

## 로컬머신 WebDAV 상태 전송

LLM Routing 서버는 현재 모델/GPU 선택 상태를 주기적으로 WebDAV에 업로드할 수 있습니다. 설정 구조는 `apps/tinyGW/pulsedav/sender.py`가 사용하는 PulseDAV 설정과 유사합니다.

예시 파일을 복사해서 실제 설정을 만듭니다. 실제 password가 들어가는 `webdav_settings.json`은 gitignore 대상입니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/llm_routing
cp webdav_settings.example.json webdav_settings.json
```

`webdav_settings.json`을 수정합니다.

```json
{
  "enabled": true,
  "schedule": {
    "interval_minutes": 30
  },
  "report": {
    "filename": "llm_routing_status.md"
  },
  "webdav": {
    "hostname": "https://nextcloud.example.com:443",
    "root": "/remote.php/dav/files/username",
    "sub": ["gpu", "llm-routing"],
    "username": "username",
    "password": "app-password-or-token",
    "verify_ssl": true
  }
}
```

서비스를 재시작하면 즉시 1회 전송하고, 이후 `schedule.interval_minutes` 간격으로 상태 파일을 업로드합니다. 설정값이 1440분보다 크더라도 하루에 한 번 이상 전송되도록 최대 대기 시간은 1440분으로 제한됩니다. 전송 파일명은 `report.filename` 뒤에 날짜와 시간이 붙은 `llm_routing_status_YYYYMMDD_HHMMSS.md` 형식으로 생성됩니다. 같은 원격 디렉토리에 90일 이상 지난 상태 파일이 있으면 새 파일을 전송하면서 함께 삭제합니다.

```bash
./stop.sh
./start.sh
```

저장 경로는 PulseDAV와 동일하게 `tinyGW/<sub>/<호스트명>/llm_routing_status_YYYYMMDD_HHMMSS.md` 형식입니다. `webdav.sub`가 배열이면 각 `sub` 경로마다 같은 상태 파일을 업로드합니다. 업로드되는 상태 파일에는 호스트명, 대표 IP, IPv4 목록, 서비스 URL이 함께 기록됩니다. 로컬머신 탭의 `LLM Routing WebDAV 전송` 영역에서 마지막 전송 시각, 저장 경로, 오류 메시지를 확인할 수 있습니다.

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
      "proxy_port": 4011,
      "model": "llama3.1",
      "api_type": "ollama",
      "gpu_info": "RTX 5090",
      "gpu_type": "NVIDIA",
      "selected_gpu": "0",
      "access_id": "",
      "password": "",
      "enabled": true
    }
  ]
}
```

`api_type`은 `ollama`, `openai`, `vllm`을 지원합니다.

`ollama` target에 `proxy_port`를 지정하면 LLM Routing 서버가 별도 Ollama 호환 reverse proxy 포트를 엽니다. 예를 들어 위 설정은 `http://LLM_ROUTING_SERVER_IP:4011/api/tags`, `http://LLM_ROUTING_SERVER_IP:4011/api/generate`, `http://LLM_ROUTING_SERVER_IP:4011/api/chat` 요청을 `http://127.0.0.1:11434`로 전달합니다. `proxy_port`가 `0`이거나 비어 있으면 프록시 포트를 열지 않습니다.

```bash
curl http://LLM_ROUTING_SERVER_IP:4011/api/tags

curl -X POST http://LLM_ROUTING_SERVER_IP:4011/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"llama3.1","prompt":"hello","stream":false}'
```

프록시 bind 주소는 기본적으로 `LLM_ROUTING_HOST`와 같으며, `LLM_ROUTING_PROXY_HOST` 환경 변수로 따로 지정할 수 있습니다. 프록시 backend 요청 timeout은 `LLM_ROUTING_PROXY_TIMEOUT`으로 조정합니다.

## Backend Type

- `ollama`: `http://HOST:PORT/api/generate`와 `http://HOST:PORT/api/tags`를 사용합니다. `/api/tags`가 없는 Gemma4OllamaServer 형태는 `/health`의 `models`, GPU, queue 정보를 fallback으로 사용합니다.
- `openai`: `http://HOST:PORT/v1/chat/completions`와 `http://HOST:PORT/v1/models`를 사용합니다.
- `vllm`: vLLM의 OpenAI 호환 서버 기준으로 `http://HOST:PORT/v1/chat/completions`, `http://HOST:PORT/v1/models`, `http://HOST:PORT/health`, `http://HOST:PORT/metrics`를 사용합니다.

GPU가 2개 이상 있는 서버는 LLM 리스트 화면에서 IP/PORT를 입력한 뒤 `모델 조회`를 누르면 `/health`의 GPU 목록을 읽어 `GPU 자동 선택` 드롭다운에 표시합니다. 특정 GPU를 선택하고 저장하면 prompt 전송 시 `selected_gpu` 값이 backend로 전달됩니다. 자동 배정을 쓰려면 `GPU 자동 선택` 상태로 저장하세요.

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

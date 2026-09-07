# Gemma4 Ollama 서버

이 디렉터리는 Ollama를 백엔드로 사용하는 Gemma4 웹 페이지와 JSON API 서버를 제공합니다.

- Gemma4 웹/API 서버 기본 포트: `8082`
- Ollama 백엔드 기본 포트: `11434`
- 기본 모델: `gemma4:31b`
- 기본 접속 주소: `http://localhost:8082`

주요 기능:

- 로컬 Ollama 서버 시작, 중지 및 상태 확인
- 필요한 Ollama 모델 자동 다운로드
- 텍스트·이미지 프롬프트 처리
- `api_key.conf` 기반 사용자 인증
- 프롬프트 이력, 사용자별 이력 및 접속 로그 저장
- 웹 UI에서 GPU와 모델 선택
- 프롬프트 컨텍스트용 작업 파일 업로드
- 서비스 포트별 독립 Ollama 인스턴스 실행

## 요구 사항

- Linux 또는 macOS
- Bash, Python 3, curl
- Ollama(없으면 시작 스크립트가 설치를 시도함)
- NVIDIA GPU 사용 시 NVIDIA 드라이버와 `nvidia-smi`

## 빠른 시작

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server
chmod +x run_service.sh start.sh stop.sh
./run_service.sh
```

브라우저에서 `http://SERVER_IP:8082`를 엽니다. `run_service.sh`는 포그라운드에서 실행되며 `Ctrl+C`로 종료합니다.

백그라운드 실행과 중지:

```bash
./start.sh
./stop.sh
```

`stop.sh`는 `server.pid`와 `ollama.pid`가 있으면 해당 프로세스를 중지합니다.

## 포트 및 다중 인스턴스

```text
./run_service.sh [서비스_포트] [GPU] [Ollama_포트] [--ai-server-list-token TOKEN]
```

실행 예시:

```bash
./run_service.sh 8083             # 서비스 포트만 변경
./run_service.sh 2500 0           # 서비스 2500, GPU 0, Ollama 12500
./run_service.sh 2501 1           # 서비스 2501, GPU 1, Ollama 12501
./run_service.sh 2500 0 11434     # Ollama 포트 직접 지정
```

서비스 포트를 지정하면 상태 파일이 `instances/ollama_<서비스_포트>/` 아래에 분리됩니다. Ollama 포트를 생략하면 `서비스 포트 + 10000`을 사용합니다. 각 인스턴스는 별도의 GPU 선택 파일, PID 파일 및 로그 디렉터리를 가집니다.

GPU 값은 숫자 인덱스(`0`, `1` 등), `auto`, `all`, `cpu`, `none` 중 하나입니다.

환경 변수로 포트를 지정할 수도 있습니다.

```bash
GEMMA4_SERVER_PORT=8084 ./run_service.sh
GEMMA4_SERVER_PORT=8083 ./start.sh
```

`start.sh`는 위치 인수로 포트를 받지 않으므로 환경 변수를 사용해야 합니다.

## 시작 과정

`run_service.sh`와 `start.sh`는 다음 작업을 수행합니다.

1. Ollama 실행 파일을 찾고, 없으면 설치를 시도합니다.
2. `gpu-selection`과 `model-selection`을 읽습니다.
3. Ollama 상태를 확인하고 필요하면 시작합니다.
4. 모델이 없고 `AUTO_PULL=1`이면 모델을 내려받습니다.
5. 서비스 포트가 사용 가능한지 확인합니다.
6. Python 웹/API 서버를 시작합니다.

`run_service.sh`는 선택 GPU를 적용하기 위해 기존 Ollama를 안전하게 재시작할 수 있습니다. 리스닝 프로세스가 실제 Ollama인지 확인하며, 스크립트가 중지한 systemd Ollama 서비스는 포그라운드 서버 종료 시 복원합니다.

## 사용자 인증

웹 페이지와 `POST /api/generate` 호출에는 `api_key.conf`에 등록된 사용자 ID와 비밀번호가 필요합니다.

```bash
cp api_key.conf.sample api_key.conf
chmod 600 api_key.conf
```

설정 예시:

```json
{
  "enabled": true,
  "allow_only_user": "",
  "users": [
    {"id": "admin", "password": "안전한-비밀번호", "enabled": true},
    {"id": "operator", "password": "다른-안전한-비밀번호", "enabled": true}
  ]
}
```

- `enabled`: 전체 인증 기능 활성화 여부
- `allow_only_user`: 특정 사용자만 허용할 때 사용자 ID 지정. 모든 활성 사용자를 허용하려면 빈 문자열 사용
- 사용자별 `enabled`: 해당 계정 활성화 여부

`api_key.conf`가 없으면 서버가 기본 파일을 만들고 가능한 경우 권한을 `0600`으로 설정합니다. 운영 환경에서는 기본 비밀번호를 반드시 변경하십시오.

API 인증은 HTTP Basic Auth, 인증된 웹 세션 쿠키 또는 JSON의 `user_id`, `password` 필드로 전달할 수 있습니다.

## 텍스트 생성 API

```bash
curl -sS -X POST http://127.0.0.1:2500/api/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "admin",
    "password": "안전한-비밀번호",
    "prompt": "현재 시간을 알려주세요"
  }' | python3 -m json.tool
```

`invalid user id or password`가 반환되면 `api_key.conf`의 활성 사용자 정보와 요청 값을 확인합니다.

프롬프트 API:

```text
POST /api/generate
POST /api/enqueue-generate
GET  /api/prompt-result?id=JOB_ID
POST /api/cancel-pending-prompts
```

## 이미지·OCR 요청

이미지는 Ollama 호환 Base64 문자열 배열로 전달합니다.

```json
{
  "user_id": "admin",
  "password": "안전한-비밀번호",
  "prompt": "이미지에서 보이는 모든 글자를 추출해 주세요.",
  "images": ["base64-image-data"],
  "model": "vision-capable-model"
}
```

이미지 입력을 지원하는 모델을 선택해야 합니다. 텍스트 전용 모델은 이미지를 무시하거나 부정확한 응답을 만들 수 있습니다.

추론 없이 이미지 전달만 시험하려면 같은 인증 정보와 `images` 배열로 `POST /api/test-image-transfer`를 호출합니다. 응답의 `image_count`로 전달된 이미지 수를 확인할 수 있습니다.

## API 목록

상태 확인:

```text
GET /health
GET /api/tags
GET /api/status
```

Ollama 제어:

```text
POST /api/start-ollama
POST /api/unload-model
POST /api/stop-ollama
```

GPU, 모델 및 세션 관리:

```text
POST /api/select-gpu
POST /api/select-model
GET  /api/session-status
POST /api/session-login
POST /api/session-logout
POST /api/save-user
```

로그, 이력 및 작업 공간:

```text
GET  /api/prompt-history
GET  /api/user-prompt-history
GET  /api/access-log
GET  /api/workspace/files
POST /api/workspace/upload
```

파일 업로드 예시:

```json
{
  "user_id": "admin",
  "password": "안전한-비밀번호",
  "files": [
    {"name": "notes.txt", "content": "프롬프트에 사용할 참고 내용"}
  ]
}
```

파일은 `workspace/`에 저장되며 같은 이름이 있으면 숫자 접미사가 붙습니다.

## GPU 및 모델 선택

웹 UI에서 선택한 값은 다음 파일에 저장됩니다.

- `gpu-selection`: `auto`, `all`, `cpu`, `none` 또는 GPU 인덱스
- `model-selection`: Ollama 모델 이름

직접 지정하는 예시:

```bash
echo 0 > gpu-selection
echo gemma4:31b > model-selection
./run_service.sh
```

숫자 GPU 인덱스를 선택하고 `nvidia-smi`를 사용할 수 있으면 인덱스를 GPU UUID로 변환해 `CUDA_VISIBLE_DEVICES`에 적용합니다. `cpu` 또는 `none`은 `CUDA_VISIBLE_DEVICES=-1`을 사용합니다.

GPU가 하나뿐인데 잘못된 인덱스를 지정하면 경고 후 유일한 GPU를 사용합니다. GPU가 여러 개인 경우에는 사용 가능한 인덱스를 표시하고 시작을 중단합니다.

## systemd 사용자 서비스

```bash
mkdir -p ~/.config/systemd/user
cp gemma4-ollama-8082.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gemma4-ollama-8082.service
systemctl --user status gemma4-ollama-8082.service
journalctl --user -u gemma4-ollama-8082.service -f
```

## macOS LaunchAgent

```bash
mkdir -p ~/Library/LaunchAgents
cp com.berepi.gemma4-ollama-8082.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.berepi.gemma4-ollama-8082.plist
launchctl enable "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
launchctl kickstart -k "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
```

중지:

```bash
launchctl bootout "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
```

## 주요 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:31b` | 기본 Ollama 모델 |
| `OLLAMA_CONTEXT_LENGTH` | `8192` | 모델 컨텍스트 길이 |
| `OLLAMA_KEEP_ALIVE` | `60m` | 모델 메모리 유지 시간 |
| `OLLAMA_BIN` | 자동 탐색 | Ollama 실행 파일 경로 |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API 주소 |
| `OLLAMA_HOST` | `127.0.0.1:11434` | Ollama 리스닝 주소 |
| `GEMMA4_SERVER_HOST` | `0.0.0.0` | 웹/API 서버 리스닝 주소 |
| `GEMMA4_SERVER_PORT` | `8082` | 웹/API 서버 포트 |
| `AUTO_PULL` | `1` | 모델 자동 다운로드 여부 |
| `API_KEY_CONF_FILE` | `api_key.conf` | 사용자 인증 설정 파일 |
| `GEMMA4_REQUEST_TIMEOUT` | `600` | 요청 제한 시간(초) |
| `GEMMA4_SESSION_TTL_SECONDS` | `28800` | 웹 세션 유효 시간(초) |
| `GEMMA4_SELECTED_MODEL` | 없음 | 선택 모델 런타임 재정의 |
| `GEMMA4_SELECTED_GPU` | 없음 | 선택 GPU 런타임 재정의 |
| `GEMMA4_CUDA_VISIBLE_USE_UUID` | 비활성 | GPU 인덱스를 UUID로 매핑 |

경로 관련 변수로 `OLLAMA_PID_FILE`, `GPU_SELECTION_FILE`, `MODEL_SELECTION_FILE`, `PROMPT_HISTORY_FILE`, `GEMMA4_ACCESS_LOG_FILE`, `GEMMA4_SAMPLE_DIR`, `GEMMA4_SERVER_WORKSPACE_DIR`, `GEMMA4_MACH_STATS_DIR`, `GEMMA4_PROMPT_PROCESS_COUNT_FILE`, `GEMMA4_LOG_DIR`을 사용할 수 있습니다.

## 실행 중 생성되는 파일

```text
api_key.conf
gpu-selection
model-selection
ollama.pid
server.pid
prompt_history.txt
instances/
logs/
workspace/
mach_stats/
```

이 항목들은 인증 정보 또는 실행 상태를 포함할 수 있으므로 일반적으로 Git에 커밋하지 않습니다.

## 문제 해결

상태 확인:

```bash
curl -fsS http://127.0.0.1:8082/health
curl -fsS http://127.0.0.1:11434/api/tags
```

로그 확인:

```bash
tail -f logs/server.log
tail -f logs/ollama.log
```

포트 충돌 시 다른 포트를 사용합니다.

```bash
./run_service.sh 8083
```

모델 자동 다운로드를 끄거나 사용법을 확인하려면 다음 명령을 사용합니다.

```bash
AUTO_PULL=0 ./run_service.sh
./run_service.sh --help
```

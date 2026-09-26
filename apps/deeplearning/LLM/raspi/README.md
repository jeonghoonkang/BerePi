# Raspberry Pi 5 · Gemma 4 E4B 서버

`../5090/run_gemma4_ollama/server`의 Ollama + Python 웹/API 구조를 참고한
독립적인 Pi용 경량 구현입니다. 기본 모델은 `gemma4:e4b`, 웹 포트는 `8082`입니다.
Python 표준 라이브러리만 사용하므로 pip/venv 설치는 필요하지 않습니다.

## 장비와 메모리

- Raspberry Pi 5 **16GB 권장**, Raspberry Pi OS 또는 Ubuntu **64비트 ARM Linux**.
- 냉각 팬, 안정적인 전원, 모델 저장용 SSD 권장. 다운로드·업데이트 여유를 포함해
  사용 가능한 저장 공간 25GB 이상을 확보하는 것을 권장합니다.
- [Ollama E4B 페이지](https://ollama.com/library/gemma4:e4b)에서 확인한 기본 모델은
  Q4_K_M이며 다운로드 크기는 약 **9.6GB**입니다(2026-09-26 확인).
  E4B의 E는 effective parameters를 뜻하며, 파일 크기가 4GB라는 뜻이 아닙니다.
  실행 시에는 모델 외에도 컨텍스트와 런타임 메모리가 필요합니다.
- 4GB/8GB Pi에서는 E4B 운영을 권장하지 않습니다. 시작 시 경고를 표시하며,
  다운로드가 성공해도 추론 시 메모리 부족으로 실패할 수 있습니다.
  필요하면 `config.env`의 `OLLAMA_MODEL=gemma4:e2b`로 변경해 별도 검증하십시오.
  스크립트는 swap이나 오버클럭 설정을 변경하지 않습니다.
- CPU 추론 기본값: 4스레드, 컨텍스트 2,048, 최대 출력 512토큰, 동시 추론 1개.
  실제 Pi에서 측정한 속도나 메모리 사용량은 아직 없습니다.

## Raspberry Pi 5 RAM 8GB에서 사용하기

여기서 8GB는 Pi의 RAM 용량입니다. **현재 기본값인 `gemma4:e4b`는 8GB Pi에서
안정적인 운영을 권장하지 않습니다.** 다운로드 크기만 약 9.6GB이고 OS와 추론
런타임에도 메모리가 필요합니다. SSD swap으로 실행을 시도할 수는 있지만,
디스크 접근으로 응답이 크게 느려지거나 메모리 부족으로 실패할 수 있습니다.
이 프로젝트는 swap을 자동 생성하거나 크기를 변경하지 않습니다.

더 작은 `gemma4:e2b`를 대안으로 시험할 수 있습니다. 다만
[공식 E2B 페이지](https://ollama.com/library/gemma4:e2b)의 다운로드 크기도
약 **7.2GB**입니다(2026-09-26 확인). 다운로드 크기는 실제 RAM 사용량과 같지 않으며,
**E2B 역시 8GB에서 동작을 보장하지 않습니다.** 아래는 실기기 검증을 위한 시작 설정입니다.

1. `server` 디렉터리에서 `bash install.sh`를 실행합니다.
2. **첫 서버 실행 전에** 생성된 `config.env`의 다음 항목을 수정합니다.
   기존 `GEMMA4_API_KEY`와 나머지 설정은 유지합니다.

   ```bash
   OLLAMA_MODEL=gemma4:e2b
   OLLAMA_CONTEXT_LENGTH=2048
   GEMMA4_NUM_THREAD=4
   GEMMA4_MAX_TOKENS=256
   AUTO_PULL=1
   ```

3. `bash run_service.sh`로 실행하면 E2B가 없을 때 자동 다운로드합니다.
   이미 실행 중이라면 `Ctrl+C`로 종료 후 다시 실행하고,
   systemd 운영 중이면 `sudo systemctl restart gemma4-raspi.service`를 사용합니다.
4. 아래 API 사용 예시로 짧은 질문을 보내 실제 추론 성공 여부를 확인합니다.
   `/ready` 성공은 모델 설치 확인이며 메모리에 로드 가능한지까지 검증하지 않습니다.

메모리가 부족하면 다른 모델과 불필요한 앱을 종료하고
`OLLAMA_CONTEXT_LENGTH=1024`, `GEMMA4_MAX_TOKENS=128`로 낮춘 후 재시작합니다.
컨텍스트를 낮추면 대화에 사용할 수 있는 길이도 줄어들며, 모델 자체의 메모리
요구량은 줄어들지 않습니다. 단일 요청에서도 실패하면 더 작은 모델을 선택하거나
RAM 16GB 장비로 전환해야 합니다. SD 카드 swap에 의존한 상시 운영은 피하십시오.

```bash
free -h
swapon --show
tail -n 100 logs/ollama.log
```

현재 시작 스크립트는 RAM이 14GiB 미만이면 모델 선택과 관계없이 E4B 기준 경고를
표시합니다. E2B로 변경한 뒤에도 이 경고가 나타날 수 있으며, 실제 선택 모델은
서버 시작 로그의 `model=gemma4:e2b`로 확인합니다. 8GB Pi에서의 속도와 안정성은
아직 실측하지 않았습니다.

## 설치 및 실행

Pi에서 일반 사용자로 실행합니다. 현재 개발 체크아웃이 macOS 경로에 있더라도
아래는 배포 대상 Pi의 경로입니다.

```bash
cd /home/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/raspi/server
bash install.sh
bash run_service.sh
```

`install.sh`는 apt 의존성을 설치하고, Ollama가 없으면
[공식 설치 스크립트](https://docs.ollama.com/linux)를 실행합니다.
임의 API 키를 포함한 `config.env`를 권한 `0600`으로 생성하며 기존 설정은 보존합니다.
Ollama 공식 설치 프로그램이 시스템 `ollama.service`를 등록/시작할 수 있습니다.
Pi 서버는 별도의 `127.0.0.1:11435` 인스턴스를 사용하며 기존 서비스는 중지하지 않습니다.
다른 인스턴스에 모델이 로드되어 있으면 Pi의 RAM을 함께 사용하므로 확인하십시오.

첫 실행에서 모델을 `server/models/`에 다운로드합니다. 시간이 오래 걸릴 수 있습니다.
기존 모델이 있으면 다운로드를 건너뜁니다. Ollama가 너무 오래되어 모델을 지원하지
않으면 공식 설치 방법으로 업데이트한 후 다시 실행하십시오.
서버가 실행되면 Pi의 브라우저에서 `http://127.0.0.1:8082`에 접속하고
`config.env`의 `GEMMA4_API_KEY` 값을 입력합니다. 키는 브라우저 저장소에 저장하지 않습니다.
포그라운드 실행은 `Ctrl+C`로 종료합니다. 실행기가 시작한 자식 프로세스만 종료합니다.

다른 PC에서 접속하려면 `config.env`의 `GEMMA4_SERVER_HOST=0.0.0.0`으로 변경 후
재시작하고 `http://PI_IP:8082`를 사용합니다. HTTP는 키를 암호화하지 않으므로
신뢰할 수 있는 LAN에서 사용하고, 외부 접속은 HTTPS 프록시 또는 SSH 터널을 사용하십시오.
Ollama의 `11435` 포트는 항상 loopback에만 바인딩됩니다.

## 부팅 시 자동 실행

먼저 위의 포그라운드 실행으로 모델 다운로드와 아래 API 추론을 확인한 뒤 종료합니다.
사용자가 `tinyos`가 아니거나 경로가 다르면 서비스 파일의 `User`,
`WorkingDirectory`, `ExecStart`를 실제 경로로 수정하십시오.

```bash
sudo install -m 644 gemma4-raspi.service /etc/systemd/system/gemma4-raspi.service
sudo systemctl daemon-reload
sudo systemctl enable --now gemma4-raspi.service
sudo systemctl status gemma4-raspi.service
journalctl -u gemma4-raspi.service -f
```

```bash
sudo systemctl stop gemma4-raspi.service
sudo systemctl restart gemma4-raspi.service
# 자동 시작 해제 및 중지
sudo systemctl disable --now gemma4-raspi.service
```

웹 서버 로그는 journal에, Ollama 로그는 `server/logs/ollama.log`에 기록됩니다.
장기간 운영 시 Ollama 로그를 logrotate 등으로 관리하십시오.
서비스는 추론 서버 또는 Ollama 종료 시 함께 정리하고 재시작합니다.
5분 내 3회 시작 실패 시 중단되므로 원인을 해결하고
`sudo systemctl reset-failed gemma4-raspi.service` 후 다시 시작합니다.

## API 사용

인증은 `Authorization: Bearer ...`입니다. 테스트 시 로컬 설정에서 키를 읽습니다.

```bash
set -a
source ./config.env
set +a
curl -fsS http://127.0.0.1:8082/health
curl -fsS http://127.0.0.1:8082/ready \
  -H "Authorization: Bearer $GEMMA4_API_KEY"
curl -fsS --max-time 1900 http://127.0.0.1:8082/api/generate \
  -H "Authorization: Bearer $GEMMA4_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"라즈베리파이의 용도를 한국어로 짧게 설명해 주세요.","stream":false}'
curl -fsS --max-time 1900 http://127.0.0.1:8082/api/chat \
  -H "Authorization: Bearer $GEMMA4_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"안녕하세요"}],"stream":false}'
```

- `GET /health`: 웹 서버 생존 확인, 인증 불필요.
- `GET /ready`: 인증 필요, Ollama 연결 및 설정된 모델 설치 여부 확인.
  모델을 메모리에 올리거나 추론하지 않으므로 **실제 실행 검증은 생성 API로** 수행합니다.
- `POST /api/generate`: `prompt`, 선택적 `system` 입력. 답변은 `response` 필드.
- `POST /api/chat`: `messages` 입력. 답변은 `message.content` 필드.
  대화 이력은 클라이언트가 전달하며 최대 32개의 텍스트 메시지를 허용합니다.
- 두 생성 API는 Ollama 응답 JSON을 반환하고 `stream:false`만 지원합니다.
  `model`을 전달한다면 서버 설정과 같아야 합니다. 입력 JSON은 최대 64KiB입니다.
- Pi 자원 보호를 위해 임의 모델·options·이미지·도구 실행 요청은 거부합니다.
  5090 버전의 사용자/비밀번호 인증, 대기열, 파일 업로드, Telegram 및 관리 API는
  이 경량 구현에 포함하지 않았으므로 기존 클라이언트를 그대로 대체하지는 않습니다.
- `401`: 잘못된 키, `400`: 지원하지 않는 입력, `413`: 본문 크기 초과,
  `429`: 다른 추론 진행 중, `502`: Ollama 오류, `504`: 추론 제한 시간 초과.
  실패 시 Ollama 로그에서 RAM 부족·모델 버전 오류를 확인하십시오.

## 설정

`server/config.env`를 수정하고 재시작합니다. 이 파일은 Bash로 읽으므로 신뢰하는
운영 사용자만 수정할 수 있게 관리하십시오. 파일 설정이 같은 이름의 환경변수보다 우선합니다.

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `GEMMA4_SERVER_HOST` | `127.0.0.1` | 웹 서버 바인딩 주소 |
| `GEMMA4_SERVER_PORT` | `8082` | 웹 포트 |
| `OLLAMA_PORT` | `11435` | 전용 Ollama 포트 |
| `OLLAMA_MODEL` | `gemma4:e4b` | 다운로드/실행 모델 |
| `OLLAMA_MODELS` | `server/models` 절대 경로 | 모델 저장 위치, SSD 경로로 변경 가능 |
| `OLLAMA_CONTEXT_LENGTH` | `2048` | 컨텍스트 토큰 수 |
| `GEMMA4_NUM_THREAD` | `4` | CPU 추론 스레드 수 |
| `GEMMA4_MAX_TOKENS` | `512` | 최대 출력 토큰 수 |
| `GEMMA4_REQUEST_TIMEOUT` | `1800` | Ollama 응답 대기 초 |
| `OLLAMA_KEEP_ALIVE` | `5m` | 요청 후 모델 메모리 유지 시간 |
| `AUTO_PULL` | `1` | 모델 없을 때 자동 다운로드 |
| `GEMMA4_API_KEY` | 설치 시 무작위 생성 | 최소 24자 |

포트가 이미 사용 중이면 기존 프로세스를 종료하지 않고 시작을 거부합니다.
`OLLAMA_MODELS`를 변경하면 서비스 사용자에게 해당 경로 쓰기 권한이 있어야 합니다.
캐시 유지·병렬성에 관한 설정은 [Ollama FAQ](https://docs.ollama.com/faq)를 참고하십시오.

## 개발 검증

```bash
cd server
python3 -m unittest -v test_server.py
bash -n install.sh run_service.sh
```

테스트는 모의 Ollama를 사용하여 인증, 준비 상태, 생성/대화 API, CPU 제한,
잘못된 입력, 동시 요청 거부 및 백엔드 오류 후 복구를 검증합니다.
ARM 설치, systemd 자동 시작, 실제 모델 추론은 대상 Pi에서 별도로 검증해야 합니다.

# Raspberry Pi 5 · Gemma 4 E4B 서버

`../5090/run_gemma4_ollama/server`의 Ollama + Python 웹/API 구조를 참고한
독립적인 Pi용 경량 구현입니다. 기본 모델은 `gemma4:e4b`, 웹 포트는 `8082`입니다.
웹/API 서버는 Python 표준 라이브러리를 사용합니다. OCR 이미지 검증에는 Pillow가 필요하며,
`install.sh`가 배포판 패키지 `python3-pil`을 설치하므로 Pi에서 pip/venv 설치는 필요하지 않습니다.

## 장비와 메모리

- Raspberry Pi 5 **8GB에서도 E4B 실행 사례가 있습니다**. 메모리 여유를 위해
  16GB를 권장하며, Raspberry Pi OS 또는 Ubuntu **64비트 ARM Linux**를 사용합니다.
- 냉각 팬, 안정적인 전원, 모델 저장용 SSD 권장. 다운로드·업데이트 여유를 포함해
  사용 가능한 저장 공간 25GB 이상을 확보하는 것을 권장합니다.
- [Ollama E4B 페이지](https://ollama.com/library/gemma4:e4b)에서 확인한 기본 모델은
  Q4_K_M이며 다운로드 크기는 약 **9.6GB**입니다(2026-09-26 확인).
  E4B의 E는 effective parameters를 뜻하며, 파일 크기가 4GB라는 뜻이 아닙니다.
  **다운로드 크기는 최소 물리 RAM 요구량이 아닙니다.** 실행 메모리는 모델 파일,
  양자화, 런타임의 로딩 방식, 컨텍스트 및 swap 사용에 따라 달라집니다.
- 8GB에서는 아래 실행 사례와 설정을 참고하십시오. 기본 Ollama 모델은 메모리 압박과
  지연이 클 수 있으며, 4GB 장비는 이 문서의 검증 대상이 아닙니다.
  스크립트는 RAM이 적으면 경고하지만 실행을 차단하지 않으며,
  swap이나 오버클럭 설정을 변경하지 않습니다.
- CPU 추론 기본값: 4스레드, 컨텍스트 2,048, 최대 출력 512토큰, 동시 추론 1개.
  실제 Pi에서 측정한 속도나 메모리 사용량은 아직 없습니다.

## Raspberry Pi 5 RAM 8GB에서 사용하기

여기서 8GB는 Pi의 RAM 용량입니다. **Pi 5 8GB와 Gemma 4 E4B의 로컬 연동은
조건부로 가능합니다.** 다운로드 크기 9.6GB만으로 실행 불가를 판단할 수 없으며,
실행 가능한 구성과 그 구성에서 얻을 수 있는 응답 속도를 함께 보아야 합니다.

### 확인한 실행 문서

아래는 2026-09-26에 확인한 실행 당사자의 보고와 프로젝트 벤치마크입니다.
모두 외부 측정이며, 이 저장소의 서버로 재현한 결과는 아닙니다.

| 자료 | Pi 5 8GB 실행 조건 | 보고된 결과와 적용 범위 |
| --- | --- | --- |
| [Ollama E4B 실행자 보고](https://www.reddit.com/r/raspberry_pi/comments/1sc8nmr/running_gemma_4_96gb_ram_req_on_rpi_5_8gb_stable/) · 2026-04-04 | Raspberry Pi OS, `gemma4:e4b` Q4_K_M, SSD swap + ZRAM, 2.8GHz 오버클럭 및 추가 냉각 | 작성자는 실행 성공을 보고하고, 댓글에서 한 요청 약 8분·평균 약 0.83토큰/초를 제시합니다. 현재 Ollama 구성에 가까운 사례지만 장기 운영 검증이나 보장 속도는 아닙니다. |
| [Potato OS Gemma 4 Pi 벤치마크](https://github.com/potato-os/core/blob/main/docs/benchmarks/gemma4-pi-benchmark-2026-04-04.md) · 2026-04-04 | NVMe SSD, 2GB ZRAM swap, `gemma-4-E4B-it-Q4_0.gguf` **4.49GiB**, `llama_cpp` 커밋 `a1cfb64` | 16K 컨텍스트의 5턴 대화에서 생성 **3.5토큰/초**, swap 493MB를 기록했습니다. 문서는 실험 단계로 표시되어 있습니다. 현재 Ollama 기본 태그와 모델 파일·런타임이 다릅니다. |

두 사례의 차이는 “E4B”라는 이름만으로 모델 크기와 속도를 단정할 수 없다는 점을
보여 줍니다. Potato OS의 수치를 현재 `ollama pull gemma4:e4b` 구성의 예상 속도로
사용해서는 안 됩니다. E4B 벤치마크 런타임은 `llama_cpp`이며, 같은 문서의
26B용 `ik_llama` 결과와도 구분해야 합니다.

Ollama 사례의 swap 용량·컨텍스트 등 모든 재현 조건이 명확한 것은 아닙니다.
2.8GHz 오버클럭은 해당 작성자의 조건이며, 실행을 위한 필수 조건으로 확인된 것은
아닙니다. 이 서버는 기본 클럭에서 먼저 검증하는 것을 전제로 합니다.

### 현재 서버로 E4B 시험하기

64비트 OS, SSD/NVMe 저장소, 냉각을 준비하고 OS에서 ZRAM 및 SSD swap 구성을
확인하십시오. ZRAM은 물리 RAM을 압축해 사용하므로 RAM 용량이 그대로 추가되는
것은 아닙니다. 실제 필요한 swap은 사용 모델과 다른 프로세스의 메모리 사용량에
따라 확인해야 합니다. 이 프로젝트는 swap을 자동 생성하거나 크기를 변경하지 않습니다.

1. `server` 디렉터리에서 `bash install.sh`를 실행합니다.
2. **첫 서버 실행 전에** 생성된 `config.env`의 다음 항목을 수정합니다.
   아래 값은 이 프로젝트에서 제안하는 보수적인 시작 설정이며, 위 벤치마크의
   재현 설정은 아닙니다. 기존 `GEMMA4_API_KEY`와 나머지 설정은 유지합니다.

   ```bash
   OLLAMA_MODEL=gemma4:e4b
   OLLAMA_CONTEXT_LENGTH=1024
   GEMMA4_NUM_THREAD=4
   GEMMA4_MAX_TOKENS=128
   GEMMA4_REQUEST_TIMEOUT=1800
   AUTO_PULL=1
   ```

3. `bash run_service.sh`로 실행하면 E4B가 없을 때 자동 다운로드합니다.
   이미 실행 중이라면 `Ctrl+C`로 종료 후 다시 실행하고,
   systemd 운영 중이면 `sudo systemctl restart gemma4-raspi.service`를 사용합니다.
4. 아래 API 사용 예시로 짧은 질문을 보내 실제 추론 성공 여부를 확인합니다.
   `/ready` 성공은 모델 설치 확인이며 메모리에 로드 가능한지까지 검증하지 않습니다.

다른 모델과 불필요한 앱을 종료하고 짧은 질문으로 시작합니다. 초기 로딩과 추론이
수분 걸릴 수 있습니다. 컨텍스트를 낮추면 대화에 사용할 수 있는 길이도 줄어들며,
모델 가중치 자체의 크기는 줄어들지 않습니다. 실행 중 RAM·swap·응답 시간을 확인해
필요한 지연 시간 안에 반복 요청이 완료되는지 검증하십시오.

```bash
free -h
swapon --show
vmstat 1
tail -n 100 logs/ollama.log
```

`vmstat 1`은 별도 터미널에서 확인하고 `Ctrl+C`로 종료합니다. SSD swap을 사용해도
계속 메모리 부족이나 허용할 수 없는 지연이 발생하면 더 작은 양자화 파일·모델 또는
16GB 장비를 검토하십시오. 16GB 권장은 메모리 여유를 위한 것이며 8GB 실행 불가를
뜻하지 않습니다.

### 더 작은 E4B 파일 또는 E2B 사용

Potato OS 사례처럼 작은 E4B GGUF를 사용하는 방법도 있습니다. 다만 현재 서버는
Ollama의 `/api/generate`, `/api/chat`, `/api/tags`를 사용하므로 llama.cpp 서버를
그대로 연결할 수 없습니다. 위 Q4_0 파일은 현재 설치 스크립트가 다운로드하는
모델이 아니며, 별도 런타임 도입 또는 Ollama에서 호환 GGUF를 등록하는 절차와
검증이 필요합니다. 이 README 변경에 런타임 전환 구현은 포함하지 않았습니다.

E2B를 시험하려면 `config.env`에서 `OLLAMA_MODEL=gemma4:e2b`로 변경하고 재시작합니다.
[공식 E2B 태그](https://ollama.com/library/gemma4:e2b)의 다운로드 크기는 약 7.2GB
(2026-09-26 확인)로, Potato OS 문서의 2.88GiB E2B GGUF와 다릅니다.
E2B 또한 태그·양자화·런타임별로 메모리 사용량을 확인해야 합니다.

현재 시작 스크립트는 RAM이 14GiB 미만이면 모델 선택과 관계없이 E4B 기준 경고를
표시하지만 실행을 차단하지 않습니다. 실제 선택 모델은 서버 시작 로그의 `model=`로
확인합니다. **이 저장소의 서버를 이용한 8GB Pi 실측은 아직 수행하지 않았습니다.**

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
기존 파일에 키가 없거나 비어 있거나 24자 미만이면 새 키를 추가합니다.
`bash install.sh --config-only`로 패키지 설치 없이 설정만 복구할 수 있습니다.
Ollama 공식 설치 프로그램이 시스템 `ollama.service`를 등록/시작할 수 있습니다.
Pi 서버는 별도의 `127.0.0.1:11435` 인스턴스를 사용하며 기존 서비스는 중지하지 않습니다.
다른 인스턴스에 모델이 로드되어 있으면 Pi의 RAM을 함께 사용하므로 확인하십시오.

첫 실행에서 모델을 `server/models/`에 다운로드합니다. 시간이 오래 걸릴 수 있습니다.
기존 모델이 있으면 다운로드를 건너뜁니다. Ollama가 너무 오래되어 모델을 지원하지
않으면 공식 설치 방법으로 업데이트한 후 다시 실행하십시오.
서버가 실행되면 Pi의 브라우저에서 `http://127.0.0.1:8082`에 접속하고
`admin` 계정으로 로그인합니다. 별도 암호를 설정하지 않았다면
`config.env`의 `GEMMA4_API_KEY` 값이 로그인 암호입니다. 암호는 브라우저 저장소에 저장하지 않습니다.
포그라운드 실행은 `Ctrl+C`로 종료합니다. 실행기가 시작한 자식 프로세스만 종료합니다.
다른 터미널에서는 같은 디렉터리의 `bash stop.sh`로 종료할 수 있습니다.
`stop.sh`는 현재 디렉터리의 실행 잠금을 보유한 `run_service.sh`를 확인한 뒤
종료 신호를 보내고 웹 서버·전용 Ollama의 정리가 끝날 때까지 기다립니다.
기존 실행 중인 서버도 재시작 없이 감지하며, 다른 Ollama 인스턴스는 종료하지 않습니다.
systemd 서비스로 실행 중이면 해당 서비스를 `systemctl stop`으로 중지합니다.
권한이 없으면 필요한 명령을 안내합니다.


웹 서버 시작 로그에는 장비의 `192.168.*` 및 `10.*` 내부 IPv4 접속 주소도 표시됩니다.
새 설치의 기본 바인딩은 `0.0.0.0`입니다. 기존 `config.env`는 보존되므로 이전 설치에서
`127.0.0.1`을 사용했다면 아래 설정을 변경해야 합니다. 주소 조회 실패는 서버 실행을 중단하지 않습니다.

다른 PC에서 접속하려면 `config.env`의 `GEMMA4_SERVER_HOST=0.0.0.0`으로 변경 후
재시작하고 `http://PI_IP:8082`를 사용합니다. HTTP는 키를 암호화하지 않으므로
신뢰할 수 있는 LAN에서 사용하고, 외부 접속은 HTTPS 프록시 또는 SSH 터널을 사용하십시오.
Ollama의 `11435` 포트는 항상 loopback에만 바인딩됩니다.

### `GEMMA4_API_KEY`가 파일에 없을 때

이전 `install.sh`는 `config.env`가 이미 있으면 파일 전체를 건너뛰었습니다.
따라서 샘플을 복사했거나 키를 삭제한 상태에서는 재설치해도 키가 생성되지 않았습니다.
수정된 설치기는 `init_config.py`로 기존 설정과 키의 유효성을 확인합니다.
환경 변수 이름은 대문자 **`GEMMA4_API_KEY`**를 사용합니다.

패키지나 모델을 다시 설치하지 않고 설정만 복구할 수 있습니다.
서버를 실행하는 일반 사용자 계정으로 다음 명령을 실행합니다.

```bash
cd /home/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/raspi/server
bash install.sh --config-only
```

- 파일이 없으면 샘플 설정과 무작위 64자 API 키로 생성합니다.
- 키가 없거나 비어 있거나 24자 미만이면 새 키를 파일 끝에 추가합니다.
  기존의 잘못된 키 줄이 남아 있어도 Bash는 마지막에 지정한 값을 사용합니다.
- 유효한 기존 키와 포트·모델 등 다른 설정은 보존합니다.
- 파일 권한은 `0600`으로 설정합니다. 키 값은 설치 로그에 출력하지 않습니다.
- 설정 파일의 Bash 문법이 잘못되었으면 덮어쓰지 않고 오류를 표시합니다.

키 값을 출력하지 않고 저장 여부와 길이를 확인하려면:

```bash
bash -c 'unset GEMMA4_API_KEY; source ./config.env; printf "API key length: %s\n" "${#GEMMA4_API_KEY}"'
stat -c '%a %n' config.env
```

새로 생성한 키의 길이는 `64`, 파일 권한은 `600`으로 표시됩니다.
기존 유효 키를 보존했다면 길이는 24자 이상일 수 있습니다.
로그인에 사용할 실제 값은 `config.env`의 마지막 `GEMMA4_API_KEY` 항목에서 확인합니다.

변경한 키를 적용하려면 서버를 재시작합니다. 직접 실행 중인 경우:

```bash
bash stop.sh
bash run_service.sh
```

systemd 서비스로 운영하는 경우:

```bash
sudo systemctl restart gemma4-raspi.service
```

재시작 후 웹에서 다시 로그인합니다. 별도 `GEMMA4_LOGIN_PASSWORD`가 없으면
`admin` 계정의 암호는 복구한 API 키입니다. 별도 로그인 암호가 설정되어 있다면
그 암호는 그대로 유지됩니다.

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

## git pull 후 웹 화면에서 재시작

Server 탭의 **로컬 접속 주소**에는 서버에서 조회한 `192.168.*` 주소를 우선 표시하고
`10.*` 주소도 링크로 표시합니다. 포트는 `GEMMA4_SERVER_PORT`를 사용합니다.
이 정보는 인증된 `GET /api/status`의 `local_urls`에도 포함됩니다. 주소가 없거나
조회에 실패하면 확인 불가를 표시하며, localhost로만 바인딩된 경우 설정 안내를 표시합니다.

1. 서버 디렉터리에서 `git pull`을 실행합니다.
2. 로그인한 웹 화면 상단의 **Restart · 서버 재시작**을 누릅니다.
3. 화면에서 재연결을 기다립니다. 새 서버가 확인되면 페이지를 자동으로 새로고침하며,
   서버 메모리의 세션은 초기화되므로 다시 로그인합니다.

버튼은 코드를 다운로드하거나 `git pull`을 실행하지 않습니다. 채팅/OCR 처리 중이면
재시작 요청을 거부하므로 완료 후 다시 누르세요. 재연결은 최대 3분간 확인합니다.
실패하면 실행 터미널 또는 systemd 로그를 확인한 뒤 새로고침합니다.
포트/바인딩 주소를 변경했다면 새 주소로 직접 접속해야 합니다.

`run_service.sh` 실행 시 웹 서버는 재시작 전용 종료 코드 75를 반환합니다.
실행기는 자신이 시작한 웹 서버·Ollama를 정리하고 실행 잠금을 해제한 뒤 자신을 다시
실행하여 최신 코드와 `config.env`를 읽습니다. systemd로 시작한 경우에도 같은 실행기를
교체하므로 별도 sudo 권한 없이 동작합니다. 다른 Ollama 인스턴스는 건드리지 않습니다.
`python3 server.py`로 직접 실행한 경우에는 웹 프로세스만 교체하며 기존 환경변수를 사용합니다.

**이 기능을 처음 반영할 때는** 기존 서버에 재시작 API가 없으므로 `git pull` 후 한 번은
수동으로 재시작해야 합니다. systemd는 `sudo systemctl restart gemma4-raspi.service`,
수동 실행은 `bash stop.sh` 후 `bash run_service.sh`를 사용합니다.
이후부터는 새 웹 버튼을 이용할 수 있습니다.

- `POST /api/restart`: 세션 또는 Bearer 인증 필요, 본문 `{}`. 승인 시 `202`와 기존
  `instance_id` 반환. 추론/재시작 진행 중이면 `409`, 다른 Origin 요청은 `403`입니다.
- `GET /api/health`: `instance_id`와 `restarting`을 포함합니다. 화면은 새 인스턴스가
  시작된 것을 확인한 뒤 새로고침하므로 아직 종료되지 않은 이전 서버를 재시작 완료로
  판단하지 않습니다.

## 웹 화면과 로그인

Server / OCR / History 탭을 제공하는 Pi용 인터페이스입니다.

- User ID / Password 로그인, 로그아웃, 8시간 HttpOnly 세션 쿠키.
- 서버 이름, OS, CPU/스레드 수, 메모리·swap, 온도, 부하, 가동 시간.
- Ollama 연결 상태, 선택 모델, 설치/로드 상태, 크기, 파라미터, 양자화와 상세 정보.
- Prompt 1 / Prompt 2를 합친 요청과 선택적 System Prompt.
- 생성 중 경과 시간, 회신 모델, 요청 모델, 서버 처리·모델 로딩 시간,
  입력/출력 토큰, 생성 속도, 종료 사유.
- 결과 복사·텍스트 저장, 최근 20개 요청 이력과 프롬프트 재사용.
  Remember History를 켜면 최근 10개 문답을 다음 요청에 포함합니다.
  이력은 페이지 메모리에만 보관하며 새로고침·로그아웃 시 삭제됩니다.
  텍스트 채팅의 64KiB 입력 제한과 컨텍스트 제한은 유지됩니다.
- OCR 탭: 클립보드 이미지 붙여넣기, JPG/PNG 선택, 미리보기, OCR 실행, 결과 복사·저장.
  OCR 이미지와 결과는 대화 이력에 넣지 않으며 로그아웃·새로고침 시 지웁니다.

기본 로그인 ID는 `admin`, 암호는 기존 `GEMMA4_API_KEY`입니다.
별도 암호를 사용하려면 `config.env`에 아래 값을 설정한 뒤 재시작합니다.
기존 Bearer API 키 인증도 계속 사용할 수 있습니다.

```bash
GEMMA4_LOGIN_USER=admin
GEMMA4_LOGIN_PASSWORD='원하는 로그인 암호'
```

- `POST /api/session-login`: `user_id`, `password`로 세션 생성.
- `GET /api/session`: 현재 로그인 상태 확인.
- `POST /api/session-logout`: 세션 폐기.
- `GET /api/status`: 인증 후 서버·모델·Ollama 상태 조회.
- `GET /api/model-info`: 인증 후 선택 모델의 Ollama 상세 정보 조회.

세션은 서버 메모리에만 저장되므로 서버 재시작 시 다시 로그인해야 합니다.
생성 API는 Ollama 원본 필드에 `elapsed_seconds`, `requested_model`을 추가합니다.
회신 모델은 백엔드가 반환한 `model` 필드를 표시합니다.

## 클립보드 이미지 OCR

1. 로그인한 뒤 **OCR** 탭을 엽니다.
2. 이미지 영역을 클릭하고 `Ctrl+V` (macOS: `⌘V`)로 이미지를 붙여넣습니다.
   클립보드 버튼, 파일 선택, 드래그 앤 드롭도 지원합니다.
3. 미리보기와 OCR 엔진을 확인하고 **Run OCR**을 누릅니다. 추가 지침은 Gemma 엔진에서 사용합니다.
4. 추출된 텍스트, 회신 모델, 소요시간, 출력 토큰을 확인하고 복사하거나 저장합니다.

HTTP 접속에서 클립보드 읽기 버튼이 제한되면 키보드 붙여넣기 또는 파일 선택을
사용합니다. 원본은 PNG/JPEG/WebP 최대 10 MiB이며 브라우저가 긴 변을 2048픽셀
이하로 조정해 PNG로 변환합니다. 전송할 PNG가 2 MiB를 넘으면 이미지를 잘라야 합니다.
이미지와 OCR 결과는 페이지 메모리에서만 보관하며 로그아웃·새로고침 시 삭제됩니다.
서버는 이미지 파일을 저장하지 않고 선택한 로컬 OCR 엔진에 전달합니다.

기본 엔진은 **Gemma 4**입니다. `engine` 인자를 생략하거나 `"engine": "gemma"`를
지정하면 설정된 Gemma 비전 모델을 사용합니다. 웹 화면도 Gemma 4를 기본 선택합니다.
모델의 `vision` 지원을 확인한 뒤 Ollama의 `/api/chat`에 이미지를 전달합니다.
Gemma 실행이 실패하거나 이미지 미지원 모델이어도 Tesseract로 자동 전환하지 않습니다.

**Tesseract는 요청 인자에 `"engine": "tesseract"`를 명시한 경우에만 실행합니다.**
웹 화면에서 Tesseract를 직접 선택하면 해당 인자를 전송합니다.
기본 `install.sh`는 Tesseract를 설치하지 않습니다. 필요한 경우에만
`bash install_ocr.sh`를 직접 실행해 한국어·영어 엔진을 설치할 수 있습니다.
이 스크립트는 Debian/Ubuntu 패키지를 `.ocr-runtime/`에 풀어 전용으로 사용하며,
apt 패키지 목록과 시스템 기본 공유 라이브러리를 이용합니다.
두 OCR 엔진 모두 일반 대화와 같은 단일 추론 잠금을 사용합니다.
Tesseract 처리 제한 시간은 90초입니다.
작은 글자나 흐린 이미지는 오인식할 수 있고, Gemma의 출력 한도에 도달한 긴 문서는
나누어 전송해야 합니다. OCR 입력은 일반 대화 이력에 포함하지 않습니다.
Gemma OCR 출력 한도는 `GEMMA4_OCR_MAX_TOKENS`(기본 2048)로 별도 설정합니다.

`POST /api/ocr`는 로그인 세션 또는 Bearer 인증이 필요합니다.
본문은 `{"image": "PNG의 순수 base64 문자열", "engine": "gemma", "instructions": "선택적 Gemma 지침"}`이며,
이미지 1개, 추가 지침 최대 4000자를 받습니다. API는 PNG/JPEG 최대 8 MiB·2천만 화소를
Pillow로 검증하고, JSON 한도는 base64 최대 길이에 64 KiB를 더한 값입니다.
브라우저는 Pi 메모리를 고려해 기존의 2048px·PNG 2 MiB 제한을 유지합니다.
`engine`은 `gemma`(기본) 또는 `tesseract`이며 `instructions`는 Gemma에서만 적용됩니다.
`prompt` 입력도 지원합니다. `prompt`나 `instructions`의 유무와 관계없이 엔진을
생략하면 Gemma를 사용합니다. `prompt`와 `instructions`를 동시에 보내면
400 오류를 반환합니다. Tesseract 실행 요청은 `{"image": "순수 base64 문자열", "engine": "tesseract"}`입니다.
`image`에 `data:image/png;base64,` 접두사는 붙이지 않습니다.
응답의 `text`와 `response`는 같은 인식 텍스트이며 `model`, `elapsed_seconds`, `eval_count`로
회신 엔진/모델과 처리 통계를 확인할 수 있습니다. `eval_count`는 Gemma에서만 제공합니다. `422`는 이미지 미지원 모델,
`429`는 다른 추론 진행 중을 의미합니다.

## API 사용

인증은 `Authorization: Bearer ...`입니다. 테스트 시 로컬 설정에서 키를 읽습니다.

```bash
set -a
source ./config.env
set +a
curl -fsS http://sonno.iptime.org:8082/api/health
curl -fsS http://sonno.iptime.org:8082/api/ready \
  -H "Authorization: Bearer $GEMMA4_API_KEY"
curl -fsS --max-time 1900 http://sonno.iptime.org:8082/api/generate \
  -H "Authorization: Bearer $GEMMA4_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"라즈베리파이의 용도를 한국어로 짧게 설명해 주세요.","stream":false}'
curl -fsS --max-time 1900 http://sonno.iptime.org:8082/api/chat \
  -H "Authorization: Bearer $GEMMA4_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"안녕하세요"}],"stream":false}'
```

- `GET /api/health` (`/health`도 호환 유지): 웹 서버 생존 확인, 인증 불필요.
- `GET /api/ready` (`/ready`도 호환 유지): 인증 필요, Ollama 연결 및 설정된 모델 설치 여부 확인.
  모델을 메모리에 올리거나 추론하지 않으므로 **실제 실행 검증은 생성 API로** 수행합니다.
- `POST /api/generate`: `prompt`, 선택적 `system` 입력. 답변은 `response` 필드.
- `POST /api/chat`: `messages` 입력. 답변은 `message.content` 필드.
  대화 이력은 클라이언트가 전달하며 최대 32개의 텍스트 메시지를 허용합니다.
- 두 생성 API는 Ollama 응답 JSON을 반환하고 `stream:false`만 지원합니다.
  `model`을 전달한다면 서버 설정과 같아야 합니다. 입력 JSON은 최대 64KiB입니다.
- `POST /api/ocr`: base64 JPG/PNG `image`, 선택적 `engine`, `prompt` 또는 `instructions` 입력.
  인식 결과는 동일한 `text`·`response` 필드. 기본 엔진은 Tesseract이며 위 호환 규칙을 따릅니다.
  이미지는 OCR API에서만 받으며 최대 8 MiB, 2,000만 화소로 제한합니다.
- Pi 자원 보호를 위해 임의 모델·options·도구 실행 요청은 거부합니다.
  대기열, 일반 파일 저장, Telegram, 다중 사용자 관리 및 GPU/모델 변경은 지원하지 않습니다.
- `401`: 잘못된 키, `400`: 지원하지 않는 입력, `413`: 본문 크기 초과,
  `429`: 다른 추론 진행 중, `502`: Ollama 오류, `504`: 추론 제한 시간 초과.
  실패 시 Ollama 로그에서 RAM 부족·모델 버전 오류를 확인하십시오.

## 외부 주소와 OCR 사용

외부 웹 주소는 `http://sonno.iptime.org:8082/`, API 기본 주소는
`http://sonno.iptime.org:8082/api`입니다. 이 주소는 **raspi 서버 자체**를 가리키며,
추론은 Pi의 전용 Ollama에서 실행합니다. `/api`에 접속하면 지원 엔드포인트 목록을 반환합니다.
로그인·세션·서버 상태·모델 정보·채팅·OCR·준비 상태·헬스 체크 모두 `/api/...`로 제공합니다.
웹 화면은 현재 접속한 서버의 `/api/`를 사용하므로 외부 도메인, 내부 IP, localhost 접속에서
동일한 세션 인증이 동작하며 브라우저가 Ollama 포트에 직접 연결하지 않습니다.

기존 Pi 설치에 이번 변경을 반영하려면 수정된 `server` 파일들을 배포한 뒤:

1. `sudo apt-get install python3-pil`로 이미지 검증 모듈을 설치합니다.
   가상환경에서 실행한다면 그 환경에도 `python3 -m pip install Pillow`가 필요합니다.
   Tesseract를 명시적으로 사용할 때만 선택적으로 `bash install_ocr.sh`를 실행합니다.
2. `config.env`의 `GEMMA4_SERVER_HOST=0.0.0.0`, `GEMMA4_SERVER_PORT=8082`를 확인합니다.
   기존 로그인 암호와 API 키는 그대로 사용합니다.
3. 서비스를 재시작합니다. systemd 사용 시 `sudo systemctl restart gemma4-raspi.service`,
   수동 실행 시 `bash stop.sh` 후 `bash run_service.sh`를 실행합니다.
4. 공유기에서 `sonno.iptime.org`가 연결된 외부 TCP 8082를 Pi의 TCP 8082로 전달해야 합니다.
   이 코드는 공유기/DDNS 설정을 자동으로 변경하지 않습니다.
5. 웹 화면에 로그인 → **OCR · 이미지 인식** 탭 → 이미지 선택/붙여넣기 → **OCR 실행**.

이미지 붙여넣기 영역에서 Ctrl+V / Cmd+V를 사용할 수 있습니다. `클립보드에서 가져오기`
버튼은 브라우저의 보안 컨텍스트와 권한 지원이 필요하므로 외부 HTTP 주소에서는
직접 붙여넣기 또는 파일 선택을 사용합니다. 선택한 이미지와 OCR 텍스트는 서버 파일로
저장하지 않습니다. 요청 처리 중에는 채팅과 OCR이 하나의 추론 슬롯을 공유합니다.
긴 문서는 출력 토큰 제한에 도달할 수 있으며 화면에 안내를 표시합니다.

OCR 기본 엔진은 Gemma 4이며, 설정된 비전 모델의 이미지 인식을 사용합니다.
Tesseract는 `engine` 인자로 명시한 요청에서만 실행됩니다.
[Ollama 공식 이미지 입력 규격](https://docs.ollama.com/capabilities/vision)에 따라
검증된 이미지를 base64 `images` 배열로 전달합니다. 실제 인식 정확도·처리 시간은
Pi에서 설치한 모델과 이미지로 확인해야 합니다.

외부 API를 직접 호출하는 예시 (`config.env`를 읽은 뒤 실행):

```bash
python3 - screenshot.png <<'PYTHON'
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

payload = {"image": base64.b64encode(Path(sys.argv[1]).read_bytes()).decode("ascii")}
request = urllib.request.Request(
    "http://sonno.iptime.org:8082/api/ocr",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json",
             "Authorization": "Bearer " + os.environ["GEMMA4_API_KEY"]},
)
with urllib.request.urlopen(request, timeout=1900) as response:
    print(json.load(response)["text"])
PYTHON
```

## 설정

`server/config.env`를 수정하고 재시작합니다. 이 파일은 Bash로 읽으므로 신뢰하는
운영 사용자만 수정할 수 있게 관리하십시오. 파일 설정이 같은 이름의 환경변수보다 우선합니다.

| 변수 | 기본값 | 의미 |
| --- | --- | --- |
| `GEMMA4_SERVER_HOST` | `0.0.0.0` | 웹 서버 바인딩 주소 |
| `GEMMA4_SERVER_PORT` | `8082` | 웹 포트 |
| `OLLAMA_PORT` | `11435` | 전용 Ollama 포트 |
| `OLLAMA_MODEL` | `gemma4:e4b` | 다운로드/실행 모델 |
| `OLLAMA_MODELS` | `server/models` 절대 경로 | 모델 저장 위치, SSD 경로로 변경 가능 |
| `OLLAMA_CONTEXT_LENGTH` | `2048` | 컨텍스트 토큰 수 |
| `GEMMA4_NUM_THREAD` | `4` | CPU 추론 스레드 수 |
| `GEMMA4_MAX_TOKENS` | `512` | 텍스트 생성 최대 출력 토큰 수 |
| `GEMMA4_OCR_MAX_TOKENS` | `2048` | OCR 최대 출력 토큰 수 |
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
python3 -m unittest discover -v -p 'test_*.py' test_init_config.py
bash -n install.sh run_service.sh
```

테스트는 모의 Ollama를 사용하여 인증, 준비 상태, 생성/대화 API, CPU 제한,
JPG/PNG OCR 이미지 전달·응답, 손상/미지원/과대 이미지 거부, 공개 호스트의 세션 인증,
동시 요청 거부 및 백엔드 오류 후 복구를 검증합니다. 테스트 실행에도 Pillow가 필요합니다.
ARM 설치, systemd 자동 시작, 실제 모델 추론은 대상 Pi에서 별도로 검증해야 합니다.


## 시작 시 연결 오류와 접속 주소

이전 실행기에서 아래 메시지 직후 `Gemma4 Pi: ...`가 출력됐다면, Ollama가 준비되기
전 첫 상태 조회가 실패한 후 재시도에 성공한 것입니다. 실행기는 Ollama API 응답과
모델 존재 여부를 확인한 다음 웹 서버를 시작합니다. 이는 실제 모델 추론 성공까지
검증했다는 뜻은 아닙니다.

```text
curl: (7) Failed to connect to 127.0.0.1 port 11435
Gemma4 Pi: http://127.0.0.1:8082 model=gemma4:e4b
```

현재 실행기는 대기 중 일시적인 curl 오류를 `server/logs/ollama-readiness.log`에
저장하고 다음처럼 준비 상태를 표시합니다. 시작 실패나 대기 시간 초과 시에는
오류를 출력하고 종료합니다. Ollama 자체의 오류는 `server/logs/ollama.log`에서 확인하세요.

```text
Waiting for Ollama: http://127.0.0.1:11435 ...
Ollama API ready: http://127.0.0.1:11435
```

`GEMMA4_SERVER_HOST=127.0.0.1`이면 Pi 자신에서만 웹 서버에 접속할 수 있습니다.
시작 로그의 LAN IP는 장비 주소 안내이며 현재 그 주소로 접속 가능하다는 의미는 아닙니다.
다른 PC에서 접속하려면 `server/config.env`를 다음과 같이 설정하고 서비스를 재시작하세요.

```bash
GEMMA4_SERVER_HOST=0.0.0.0
```

그 후 브라우저에서 `http://PI_IP:8082`로 접속합니다. Ollama의 `11435` 바인딩은
그대로 loopback으로 유지합니다. API 요청에는 기존 `GEMMA4_API_KEY`가 필요합니다.
Pi 안에서 웹 서버의 실행 여부는 `curl -fsS http://127.0.0.1:8082/api/health`로 확인할 수 있습니다.
메모리 경고는 실행을 차단하지 않으며, 실제 추론 성공 여부는 요청을 보내 확인해야 합니다.

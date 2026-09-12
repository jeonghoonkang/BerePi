# 소노넷 Ubuntu Fleet OCR Starter

여러 Ubuntu 장비가 **외부로만 접속**하여 중앙 설정을 주기적으로 적용하고,
Nextcloud 사진을 동기화한 뒤 Gemma 4 31B로 OCR하며, 장비 상태를 중앙에
기록하는 시작 프로젝트입니다.

## 권장 구성

```text
관리자 -> Git 저장소(Gitea/GitLab 등) <- ansible-pull timer <- Ubuntu 장비
                                                    |
Nextcloud <-> inbox / ocr-results <- pipeline timer -+
                                                    |
Gemma 4 31B vLLM API <-------------------------------+
                                                    |
중앙 Fleet API(HTTPS) <- heartbeat timer ------------+
```

- `ansible-pull`: 30분마다 Git의 플레이북을 가져와 장비를 원하는 상태로 복구합니다.
- `sononet-pipeline`: 10분마다 `Nextcloud sync -> OCR -> Nextcloud sync`를 실행합니다.
- `sononet-heartbeat`: 5분마다 서비스 결과, 디스크, OCR 처리량, 설정 버전을 중앙에 기록합니다.
- 모든 실행 로그는 각 장비의 systemd journal에 남습니다.
- 장비는 inbound SSH 포트를 열지 않아도 됩니다. HTTPS 443 outbound만 허용하면 됩니다.

## 디렉터리 구조

```text
bootstrap/install.sh                     최초 1회 설치
local.yml                                ansible-pull 진입점
roles/sononet_edge/                      Ubuntu 클라이언트 역할
central/api/                             중앙 heartbeat API
central/compose.yaml                     API + HTTPS(Caddy)
central/make_device_token.py             장비별 토큰 생성
examples/device.env.example              장비 설정 예시
```

## 1. 중앙 상태 서버 설치

DNS에서 `fleet.example.com`을 서버 IP에 연결한 후 다음을 실행합니다.

```bash
cd central
cp .env.example .env
# .env의 도메인과 두 비밀값을 반드시 교체
docker compose up -d --build
curl https://fleet.example.com/healthz
```

장비 토큰은 중앙 서버의 `FLEET_HMAC_SECRET`으로 생성합니다.

```bash
cd central
set -a; . ./.env; set +a
python3 make_device_token.py SN-000001
```

장비 ID별 토큰을 공장 출하 단계에서 해당 장비에만 넣습니다. 중앙 HMAC 비밀값을
장비에 복사하면 안 됩니다.

최근 상태 조회:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://fleet.example.com/v1/devices
```

장비의 배포·파이프라인 이벤트 조회:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \\
  \'https://fleet.example.com/v1/devices/SN-000001/events?limit=100\'
```

## 2. Ansible 저장소 준비

이 디렉터리를 Git 저장소에 올리고 `stable` 브랜치를 만듭니다. 플레이북 저장소에는
Nextcloud 비밀번호, 장비 토큰, Hugging Face 토큰을 넣지 않습니다.

사설 저장소를 쓰면 출하 시 read-only deploy key와 `known_hosts`를 설치하십시오.
대규모 운영에서는 `canary` 브랜치에 먼저 5~10대를 배정하고 검증 후 `stable`에
병합하는 방식을 권장합니다.

## 3. 장비 최초 설치

장비마다 예시 설정을 복사하고 값을 채웁니다.
비밀번호에 공백이나 셸 특수문자가 있으면 값을 작은따옴표로 감싸십시오.

```bash
sudo install -m 0600 examples/device.env.example /root/sononet-device.env
sudoedit /root/sononet-device.env
sudo bash bootstrap/install.sh /root/sononet-device.env
```

설치 후 확인:

```bash
systemctl list-timers 'sononet-*'
systemctl status sononet-pipeline.timer sononet-heartbeat.timer sononet-ansible-pull.timer
journalctl -u sononet-pipeline.service -n 100 --no-pager
journalctl -u sononet-heartbeat.service -n 100 --no-pager
```

즉시 시험 실행:

```bash
sudo systemctl start sononet-pipeline.service
sudo systemctl start sononet-heartbeat.service
```

## 4. Nextcloud 폴더 규칙

기본 원격 경로는 `/Fleet/<장비ID>`입니다.
Nextcloud에서 장비별 원격 폴더와 `inbox` 폴더를 먼저 만들고 사진을 넣습니다.

```text
Fleet/SN-000001/
  inbox/          사용자가 넣는 원본 사진
  ocr-results/    장비가 생성하는 .ocr.txt와 .ocr.json
```

`nextcloudcmd`는 단발성 양방향 동기화 도구이므로 systemd timer가 주기를 담당합니다.
OCR 작업기는 `inbox`만 읽기 때문에 결과 파일을 다시 OCR하지 않습니다. 파일 경로,
SHA-256, 모델, 프롬프트 버전을 SQLite에 기록해 같은 파일의 중복 처리를 막습니다.

## 5. Gemma 4 31B 추론 서버

기본 설계는 여러 판매 장비에 31B 모델을 중복 설치하지 않고, GPU 서버 한 곳에서
OpenAI 호환 vLLM API로 제공하는 방식입니다. 모델 사용 승인을 받은 Hugging Face
토큰으로 서버를 준비한 뒤 다음과 같이 실행할 수 있습니다.

```bash
python3 -m venv /opt/vllm
/opt/vllm/bin/pip install --upgrade vllm
HF_TOKEN=... /opt/vllm/bin/vllm serve google/gemma-4-31B-it \
  --host 127.0.0.1 --port 8000 --api-key 'CHANGE-ME'
```

실제 운영에서는 추론 API도 Caddy/Nginx 뒤에 두고 TLS를 적용하십시오. 장비의
`OCR_API_BASE_URL`에는 HTTPS 주소를, `OCR_API_KEY`에는 API 키를 넣습니다.

Gemma 4 31B 원본 가중치는 약 62.6 GB이므로 GPU 메모리, 양자화, tensor parallel
구성을 사전 검증해야 합니다. 각 장비가 충분한 GPU를 갖춘 경우에만
`OCR_API_BASE_URL=http://127.0.0.1:8000`으로 바꿔 로컬 추론할 수 있습니다.

## 운영상 중요한 사항

1. **정확도**: 생성형 VLM은 글자를 누락하거나 만들어낼 수 있습니다. 계약서·계량값
   등 중요 문서는 PaddleOCR/Tesseract와 교차검증하고 원본 이미지·해시를 보존하십시오.
2. **보안**: Nextcloud는 사용자 비밀번호 대신 장비별 app password를 사용하고,
   `/etc/sononet/device.env`는 `0600 root:root`를 유지하십시오.
3. **업데이트**: Git 커밋 서명 검증을 사용하려면 장비에 신뢰할 GPG 공개키를 배포하고
   `SONONET_VERIFY_COMMIT=1`로 설정하십시오.
4. **장애 복구**: systemd timer의 `Persistent=true` 때문에 장비가 꺼져 있던 동안 놓친
   작업은 부팅 후 실행됩니다. 같은 서비스의 중복 실행은 `flock`으로 막습니다.
5. **규모 확장**: 수백 대까지는 SQLite 상태 API로 시작할 수 있지만, 장기 보존과 다중
   API 인스턴스가 필요하면 PostgreSQL로 바꾸고 Grafana/Loki를 추가하십시오.

## 주요 설정 변경

주기는 역할 기본값에서 바꿀 수 있습니다.

```yaml
# roles/sononet_edge/defaults/main.yml
sononet_pull_interval: 30min
sononet_pipeline_interval: 10min
sononet_heartbeat_interval: 5min
```

설정 변경 후 Git에 커밋하면 장비가 다음 ansible-pull 주기에 자동 반영합니다.

## 공식 문서

- Ansible pull: https://docs.ansible.com/projects/ansible-core/devel/cli/ansible-pull.html
- Nextcloud command-line client: https://docs.nextcloud.com/server/latest/admin_manual/desktop/commandline.html
- Gemma 4 이미지 입력: https://ai.google.dev/gemma/docs/capabilities/vision/image
- Gemma 4 31B 모델: https://huggingface.co/google/gemma-4-31B-it

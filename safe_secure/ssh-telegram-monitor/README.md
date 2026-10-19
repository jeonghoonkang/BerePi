# SSH Telegram Monitor

SSH 인증 실패/성공 기록을 SQLite에 누적하고, 매일 Telegram으로 전날 및 누적 통계를 보냅니다.
Telegram 개인 채팅에서는 날짜나 IP를 질문할 수 있습니다.

## 명령

```bash
python3 ssh_monitor.py sync
python3 ssh_monitor.py query 3일전
python3 ssh_monitor.py query 59.14.241.229 언제부터
python3 ssh_monitor.py send
python3 ssh_monitor.py send 오늘
python3 ssh_monitor.py send 59.14.241.229 언제부터
python3 ssh_monitor.py daily
```

`send`는 실행한 순간 최신 SSH 로그를 동기화한 뒤 Telegram으로 바로 전송합니다. 조회어를
생략하면 오늘 현재까지의 통계와 누적 통계를 함께 보내며, `오늘`, `어제`, `누적`, 날짜 또는
IP를 지정하면 해당 조회 결과만 보냅니다. 수동 `send`는 통계 확인만 수행하고 UFW 자동
차단은 실행하지 않습니다.

Telegram에서 즉시 전체 현황을 확인하려면 `/ssh_now`를 입력하십시오. 특정 기간이나 IP는
기존처럼 `/ssh 오늘`, `/ssh 3일전`, `/ssh 누적`, `/ssh 59.14.241.229 언제부터`로 확인할
수 있습니다. 두 명령 모두 허용된 개인 채팅에서만 응답합니다.

## 매일 오전 7시 자동 전송 등록

아래 예시의 `USERNAME`은 실제 실행 계정으로, `/home/USERNAME`은 해당 계정의 실제 홈 경로로,
`/path/to/BerePi`는 저장소의 실제 절대 경로로 바꾼 뒤 실행하십시오.
systemd 서비스 파일 안의 값도 동일하게 바꿔야 합니다.
한국 시간으로 매일 오전 7시에 전날 SSH 접속 통계를 `telegram-send`로 전송합니다.
`send 어제`는 통계 전송만 수행하며 UFW 자동 차단은 실행하지 않습니다.

### 1. Telegram 실행 파일과 설정 확인

`USERNAME` 계정에서 실행합니다.

```bash
test -x /home/USERNAME/.local/bin/telegram-send && echo "telegram-send 확인"
test -f /home/USERNAME/.config/telegram-send.conf && echo "Telegram 설정 확인"
```

실행 파일이 설치되어 있으나 설정 파일이 없다면 다음 명령으로 설정합니다.

```bash
/home/USERNAME/.local/bin/telegram-send --configure
```

### 2. SSH 로그 읽기 권한 부여

```bash
sudo usermod -aG adm,systemd-journal USERNAME
```

아래 systemd 서비스는 시작할 때 변경된 그룹 권한을 적용받습니다.

### 3. 전송 서비스 등록

저장소의 기존 서비스 파일에는 환경별 경로와 `daily` 명령이 있으므로,
다음과 같이 현재 경로와 통계 전송 전용 명령으로 시스템 서비스를 작성합니다.
기존에 같은 이름의 서비스를 설치했다면 이 명령은 해당 설정을 덮어씁니다.

```bash
sudo tee /etc/systemd/system/ssh-telegram-daily.service > /dev/null <<'EOF'
[Unit]
Description=Send yesterday SSH statistics to Telegram
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=USERNAME
Environment=HOME=/home/USERNAME
Environment=TZ=Asia/Seoul
WorkingDirectory=/path/to/BerePi/safe_secure/ssh-telegram-monitor
ExecStart=/usr/bin/python3 /path/to/BerePi/safe_secure/ssh-telegram-monitor/ssh_monitor.py send 어제
EOF
```

### 4. 매일 오전 7시 타이머 등록

```bash
sudo tee /etc/systemd/system/ssh-telegram-daily.timer > /dev/null <<'EOF'
[Unit]
Description=Send SSH statistics every morning at 07:00 KST

[Timer]
OnCalendar=*-*-* 07:00:00 Asia/Seoul
Persistent=true
Unit=ssh-telegram-daily.service

[Install]
WantedBy=timers.target
EOF
```

`Persistent=true`이므로 오전 7시에 장비가 꺼져 있었다면 다음 부팅 후 누락된 작업을
한 번 실행합니다. 이때도 전송 내용은 실제 실행일 기준 전날 통계입니다.

### 5. 설정 적용 및 수동 전송 확인

다음 `start` 명령은 실제로 Telegram 메시지를 한 번 전송합니다.

```bash
sudo systemctl daemon-reload
sudo systemctl start ssh-telegram-daily.service
sudo systemctl status ssh-telegram-daily.service --no-pager
```

일회성 서비스이므로 성공 후 `inactive (dead)`로 표시되어도 정상입니다.
`status=0/SUCCESS`인지 확인합니다. 오류가 있으면 다음 로그를 확인합니다.

```bash
sudo journalctl -u ssh-telegram-daily.service -n 50 --no-pager
```

### 6. 자동 전송 활성화 및 다음 실행 확인

```bash
sudo systemctl enable --now ssh-telegram-daily.timer
sudo systemctl restart ssh-telegram-daily.timer
systemctl list-timers --all ssh-telegram-daily.timer
```

`NEXT`에 다음 실행 시각이 표시되면 등록 완료입니다. 표시 시각은 조회하는 시스템의
시간대를 따르지만 실행 기준은 위에 지정한 `Asia/Seoul`입니다.
같은 전송 작업을 crontab에 등록했다면 중복 전송을 막기 위해 해당 항목을 제거합니다.
자동 전송만 사용한다면 `ssh-telegram-bot.service`는 등록할 필요가 없습니다.

자동 전송을 중지하려면 다음 명령을 실행합니다.

```bash
sudo systemctl disable --now ssh-telegram-daily.timer
```

## 데이터와 로그

데이터와 로그는 `~/.local/share/ssh-telegram-monitor/`에 저장됩니다.

- `events.sqlite3`: 누적 이벤트 DB
- `daily-reports.log`: 매일 발송한 보고서
- `monitor.log`: 실행 및 오류 로그

텍스트 로그는 크기 제한이 있습니다. `monitor.log`는 5 MiB 단위로 최대 10개 백업,
`daily-reports.log`는 10 MiB 단위로 최대 12개 백업을 보관합니다. 오래된 백업부터
자동 삭제되므로 텍스트 로그가 무한히 증가하지 않습니다. 누적 날짜/IP 질의의 원본인
SQLite DB는 정확한 누적 통계를 위해 회전하지 않습니다.

## UFW 자동 차단

`daily` 명령으로 보고할 때 전날 인증 실패가 50회 이상인 상위 10개 공인 IP를 UFW에 추가합니다.
기본 허용 목록인 `10.0.0.0/24`, loopback 및 모든 비공인 IP는 차단하지 않습니다.
이미 차단된 주소는 중복 등록하지 않으며 결과는 Telegram 보고서에 포함됩니다.

root 권한을 최소화하기 위해 검증용 helper를 root 소유 경로에 설치하십시오.

```bash
cd /path/to/BerePi/safe_secure/ssh-telegram-monitor
sudo install -o root -g root -m 0755 ssh-monitor-ufw-block /usr/local/sbin/ssh-monitor-ufw-block
sudo install -o root -g root -m 0440 ssh-monitor-ufw.sudoers /etc/sudoers.d/ssh-monitor-ufw
sudo visudo -cf /etc/sudoers.d/ssh-monitor-ufw
```

환경변수 `SSH_MONITOR_UFW_THRESHOLD`, `SSH_MONITOR_UFW_LIMIT`,
`SSH_MONITOR_UFW_ALLOWLIST`로 기준, 최대 개수, 쉼표 구분 허용 네트워크를 조정할 수 있습니다.
UFW가 비활성 상태라면 규칙은 등록되지만 실제 패킷 차단은 UFW 활성화 후 시작됩니다.

### 차단 이후의 로그

UFW에서 IP를 차단하면 패킷이 SSH 서버에 도달하기 전에 폐기됩니다. 따라서 해당 IP의
후속 로그인 시도는 `/var/log/auth.log` 및 SSH systemd 저널에 나타나지 않으며, 이
프로그램의 SSH 인증 실패 통계에도 추가되지 않습니다. Telegram 보고서의 IP별 실패 횟수는
해당 주소가 UFW에 차단되기 전까지 SSH에 도달한 횟수입니다.

차단 이후에도 패킷 재시도를 확인하려면 UFW 로깅을 활성화하십시오. 공격량이 많으면 로그가
빠르게 증가할 수 있으므로 기본적으로 `low` 수준을 권장합니다.

```bash
sudo ufw logging low
sudo journalctl -k --grep='UFW BLOCK'
sudo grep 'UFW BLOCK' /var/log/ufw.log
```

배포 환경에 따라 `/var/log/ufw.log`가 없고 커널 저널에만 기록될 수 있습니다. 현재 버전은
UFW 차단 로그를 SQLite나 Telegram 통계에 합산하지 않습니다. 즉, 보고서는 다음 중 첫 번째
항목만 집계합니다.

- UFW를 통과해 SSH 인증 단계까지 도달한 공격
- UFW에서 사전에 폐기된 패킷(현재 미집계)

UFW 로깅을 활성화하지 않아도 차단 기능에는 영향이 없습니다. 로깅은 관측용 기능입니다.

최초 실행은 보관된 `auth.log*`에서 최근 30일을 가져옵니다. 이후에는 마지막 systemd 저널
커서부터 증분 수집합니다. Telegram 그룹에서 일반 문장을 받으려면 BotFather의
privacy mode 설정이 영향을 줄 수 있으므로 `/ssh 3일전`, `/ssh 누적`,
`/ssh 59.14.241.229 언제부터` 형식을 사용하십시오.

# SSH Telegram Monitor

SSH 인증 실패/성공 기록을 SQLite에 누적하고, 매일 Telegram으로 전날 및 누적 통계를 보냅니다.
Telegram 개인 채팅에서는 날짜나 IP를 질문할 수 있습니다.

## 명령

```bash
python3 ssh_monitor.py sync
python3 ssh_monitor.py query 3일전
python3 ssh_monitor.py query 59.14.241.229 언제부터
python3 ssh_monitor.py daily
```

## 매일 자동 전송

`ssh-telegram-daily.timer`는 매일 오전 7시에 보고서 전송을 시작합니다. 실행 부하를
분산하기 위해 실제 실행 시각은 최대 5분까지 무작위로 지연될 수 있습니다. 장비가 해당
시간에 꺼져 있었으면 `Persistent=true` 설정에 따라 다음 부팅 후 누락된 작업을 실행합니다.

타이머를 설치하고 자동 실행을 활성화하려면 다음 명령을 사용합니다.

```bash
sudo cp ssh-telegram-daily.service ssh-telegram-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ssh-telegram-daily.timer
```

이미 타이머를 설치한 장비에서 시간 설정을 갱신한 경우 파일을 다시 복사한 다음 타이머를
재시작합니다.

```bash
sudo systemctl daemon-reload
sudo systemctl restart ssh-telegram-daily.timer
systemctl list-timers ssh-telegram-daily.timer
```

데이터와 로그는 `~/.local/share/ssh-telegram-monitor/`에 저장됩니다.

- `events.sqlite3`: 누적 이벤트 DB
- `daily-reports.log`: 매일 발송한 보고서
- `monitor.log`: 실행 및 오류 로그

텍스트 로그는 크기 제한이 있습니다. `monitor.log`는 5 MiB 단위로 최대 10개 백업,
`daily-reports.log`는 10 MiB 단위로 최대 12개 백업을 보관합니다. 오래된 백업부터
자동 삭제되므로 텍스트 로그가 무한히 증가하지 않습니다. 누적 날짜/IP 질의의 원본인
SQLite DB는 정확한 누적 통계를 위해 회전하지 않습니다.

## UFW 자동 차단

매일 보고할 때 전날 인증 실패가 50회 이상인 상위 10개 공인 IP를 UFW에 추가합니다.
기본 허용 목록인 `10.0.0.0/24`, loopback 및 모든 비공인 IP는 차단하지 않습니다.
이미 차단된 주소는 중복 등록하지 않으며 결과는 Telegram 보고서에 포함됩니다.

root 권한을 최소화하기 위해 검증용 helper를 root 소유 경로에 설치하십시오.

```bash
cd /home/tinyos/devel_opment/BerePi/safe_secure/ssh-telegram-monitor
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

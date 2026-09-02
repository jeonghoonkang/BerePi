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

데이터와 로그는 `~/.local/share/ssh-telegram-monitor/`에 저장됩니다.

- `events.sqlite3`: 누적 이벤트 DB
- `daily-reports.log`: 매일 발송한 보고서
- `monitor.log`: 실행 및 오류 로그

텍스트 로그는 크기 제한이 있습니다. `monitor.log`는 5 MiB 단위로 최대 10개 백업,
`daily-reports.log`는 10 MiB 단위로 최대 12개 백업을 보관합니다. 오래된 백업부터
자동 삭제되므로 텍스트 로그가 무한히 증가하지 않습니다. 누적 날짜/IP 질의의 원본인
SQLite DB는 정확한 누적 통계를 위해 회전하지 않습니다.

최초 실행은 보관된 `auth.log*`에서 최근 30일을 가져옵니다. 이후에는 마지막 systemd 저널
커서부터 증분 수집합니다. Telegram 그룹에서 일반 문장을 받으려면 BotFather의
privacy mode 설정이 영향을 줄 수 있으므로 `/ssh 3일전`, `/ssh 누적`,
`/ssh 59.14.241.229 언제부터` 형식을 사용하십시오.

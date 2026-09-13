# 10분 간격 시스템 상태 기록

Python 표준 라이브러리만 사용합니다. `time_check.py`는 한 번 기록하고 종료하며,
`install_cron.py`는 현재 사용자의 기존 cron을 보존하고 10분 간격 및 부팅 30초 후 실행을 등록합니다.

스크립트가 있는 디렉터리에서 실행합니다.

```bash
python3 time_check.py
python3 install_cron.py
```

직접 등록하려면 `crontab -e`를 실행하고 아래 내용을 추가합니다.
`/path/to/time_check`는 스크립트가 있는 실제 절대 경로로 바꾸세요.
`install_cron.py`로 이미 등록했다면 중복으로 추가하지 않습니다.

```cron
# 매시 0, 10, 20, 30, 40, 50분에 실행
*/10 * * * * /usr/bin/python3 /path/to/time_check/time_check.py

# 부팅 후 30초 대기한 뒤 실행
@reboot /bin/sleep 30 && /usr/bin/python3 /path/to/time_check/time_check.py
```

등록된 내용은 `crontab -l`로 확인합니다.

기본 저장 위치: 스크립트 디렉터리 아래 `log/`
파일 예: `health_20260913_181550_860782+0900.json` (장비 현지 시간, 마이크로초, 시간대).
각 실행 시 365일보다 오래된 이 프로그램의 날짜 형식 JSON 파일만 삭제합니다.
`.state.json`은 직전 측정 상태, `.lock`은 중복 실행 방지용입니다.
원자적 파일 교체와 fsync로 기록 손상 위험을 줄입니다.

- CPU: 온도, 측정 시점 1초 평균 사용률, 같은 부팅 내 직전 기록 이후 평균 사용률(0~100%).
- 전원: 커널 `rpi_volt` 저전압 경보 및 가능한 경우 `vcgencmd get_throttled` 현재/부팅 이후 이상 플래그.
  읽지 못한 정보는 null과 오류로 남기며 정상으로 판단하지 않습니다.
  저전압 경보가 없다는 것은 측정 시점의 관측 결과이며 전원 안정성을 보증하지 않습니다.
- 네트워크: 기본 경로의 인터페이스, 루프백을 제외한 인터페이스별 누적 RX/TX 바이트,
  직전 기록 대비 바이트 증가량과 해당 구간 평균 Mbps, 오류/드롭 카운터.
  LAN/인터넷 트래픽이 함께 집계되므로 인터넷 전용 사용량이 아닙니다.
  최초 기록·재부팅·인터페이스 교체/카운터 감소 시 증가량은 null입니다.
  기본 경로가 없어도 인터페이스 카운터를 기록하며 인터넷 접속 성공을 검증하지는 않습니다.
- 재부팅: boot_id, 가동 시간, 추정 부팅 시각, 직전 기록 시각, 기록 사이 시간차.
  재부팅이면 event=boot_changed, 15분 초과 기록 공백이면 missed_interval_suspected=true.
- 커널: 접근 가능한 최근 11분/최대 500줄에서 전원·과열·OOM·저장장치 오류 관련 메시지를 추립니다.

갑작스러운 전원 차단 시점이나 원인은 이 장비 자체에서 확정할 수 없습니다.
마지막 로그와 다음 부팅 로그로 중단 가능 구간을 확인합니다. 기록 공백은 cron 실패나
시계 변경으로도 생길 수 있습니다. 종료 직전 훼손이나 저장장치 고장은 fsync로 완전히 방지되지 않습니다.
1년 보관 시 약 52,560개 정기 로그가 생깁니다.

현재 장비에서는 일반 사용자 `vcgencmd` 접근이 실패합니다. 커널의 `rpi_volt` 경보는 읽을 수 있으며,
펌웨어의 부팅 이후 이력은 확인 불가(null)로 기록됩니다. 권한이나 장치 설정을 변경하지 않습니다.

플래그 정의: https://www.raspberrypi.com/documentation/computers/os.html#get_throttled

등록 해제는 `crontab -e`에서 `# BEGIN BerePi time_check`부터 `# END BerePi time_check`까지 삭제합니다.
수동 실행도 이전 측정 기준을 갱신하므로 증가량의 실제 `interval_seconds`를 함께 확인하세요.

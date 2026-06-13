# Port Scan

로컬 시스템에서 열려 있는 TCP listening 포트를 출력하는 도구입니다.

## 실행

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/port_scan
./run.sh
```

기본 실행은 `lsof`, `ss`, `netstat` 중 사용 가능한 명령으로 현재 listening 포트를 조회합니다.

실제 TCP connect 방식으로 포트 범위를 스캔하려면:

```bash
./run.sh --scan
./run.sh --scan --host 127.0.0.1 --start 1 --end 1024
./run.sh --scan --max-duration 5
```

## 옵션

- `--scan`: OS socket 목록 조회 대신 TCP connect 방식으로 검사합니다.
- `--host`: `--scan`에서 검사할 호스트입니다. 기본값은 `127.0.0.1`입니다.
- `--start`: `--scan` 시작 포트입니다. 기본값은 `1`입니다.
- `--end`: `--scan` 종료 포트입니다. 기본값은 `65535`입니다.
- `--timeout`: 포트당 connect timeout 초입니다. 기본값은 `0.2`입니다.
- `--max-duration`: 스캔 최대 실행 시간(초)입니다. 시간이 초과되면 남은 포트는 건너뛰고 찾은 결과만 출력합니다. 기본값은 `10.0`입니다.
- `--workers`: 병렬 검사 worker 수입니다. 기본값은 `256`입니다.

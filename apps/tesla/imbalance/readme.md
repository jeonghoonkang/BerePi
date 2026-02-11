## Tesla 배터리 imbalance 수집 앱

Tesla 차량 API(`vehicle_data`의 `charge_state`)를 주기적으로 호출해 배터리 관련 값을 SQLite에 저장합니다.

### 저장 항목
- `battery_level`
- `usable_battery_level`
- `soc_gap` (`battery_level - usable_battery_level`)
- API 응답에 존재할 경우 `battery_imbalance` / `cell_imbalance` 계열 값
- `charge_state` 원본 JSON

> 참고: Tesla API/차량 펌웨어에 따라 imbalance 전용 필드가 없을 수 있습니다. 이 경우에도 SOC gap 및 원본 charge state를 계속 저장합니다.

### 사용 방법
```bash
cd apps/tesla/imbalance
cp .env.example .env
# .env 에서 TESLA_ACCESS_TOKEN, TESLA_VEHICLE_ID 수정
docker compose up -d --build
```

### 데이터 확인
```bash
sqlite3 ./data/imbalance.db "SELECT collected_at_utc, battery_level, usable_battery_level, soc_gap, imbalance_value FROM battery_imbalance ORDER BY id DESC LIMIT 20;"
```

### 파일 구성
- `collector.py`: Tesla API 조회 및 DB 저장 루프
- `docker-compose.yml`: 컨테이너 실행 설정
- `Dockerfile`: Python 런타임 이미지
- `.env.example`: 환경변수 샘플

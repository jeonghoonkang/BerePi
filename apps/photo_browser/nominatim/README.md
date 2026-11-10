# Photo Browser Nominatim Docker

Photo Browser의 Nominatim 실행은 Docker 방식만 지원합니다. 호스트 소프트웨어 스택 설치 스크립트와 로컬 Python 서버 실행기는 제거했습니다. 호스트에 이미 설치된 패키지·DB를 자동으로 삭제하지는 않습니다.

## 실행

로컬 Docker Engine 또는 Docker Desktop이 필요합니다. 현재 사용자로 다음 명령이 성공해야 합니다.

```bash
docker info
```

저장소 루트에서 Photo Browser를 시작합니다.

```bash
python3 apps/photo_browser/app.py \
  --host 0.0.0.0 --port 7078 --root / \
  --nominatim-docker
```

평소 사용하는 `--directory`, `--db`도 함께 지정하세요. 기본 구성은 다음과 같습니다.

| 항목 | 기본값 |
| --- | --- |
| 이미지 | `mediagis/nominatim:5.3` |
| 지도 | 한국 Geofabrik PBF |
| DB 영구 볼륨 | `photo-browser-nominatim-5-3` |
| 볼륨의 컨테이너 내부 경로 | `/var/lib/postgresql/16/main` |
| 조회 주소 | `http://127.0.0.1:8080/reverse` |
| 준비 대기 | 7200초 |

이미지는 [mediagis Nominatim Docker](https://github.com/mediagis/nominatim-docker)를 사용합니다. 첫 실행에는 이미지와 지도를 내려받아 행정구역 중심(`IMPORT_STYLE=admin`), 역지오코딩 전용(`REVERSE_ONLY=true`) DB를 가져옵니다. PostgreSQL과 Nominatim은 컨테이너 안에서 실행되며, 호스트에 직접 설치하지 않습니다. Docker 볼륨은 Docker 데몬이 관리하는 위치에 저장되며 Photo Browser의 JSON DB와는 별개입니다.

Photo Browser 웹서버는 Nominatim 준비를 기다리지 않고 시작하므로, 지도 다운로드 중에도 Nominatim 탭에 접속할 수 있습니다. 상태 API의 `status`가 `0`이 되면 위치 조회 준비 완료로 표시합니다. 컨테이너 로그는 실행 터미널에도 표시합니다. 최초 가져오기는 데이터 크기·서버 성능에 따라 오래 걸릴 수 있습니다.

지도 파일 다운로드 중에는 이미지의 curl 진행 로그를 읽어 **진행률, 받은 용량/전체 용량, 속도, 경과 시간, 예상 남은 시간, 다운로드 완료 예상 시각(로컬 시간대)**을 함께 출력합니다. 약 2초 간격으로 갱신하며 완료 진행률도 표시합니다. 서버가 파일 크기나 속도를 제공하지 않으면 예상 시각은 `계산 중`입니다. 사용자 지정 이미지가 같은 로그 형식을 제공하지 않으면 원본 로그와 준비 대기 안내를 확인하세요.

다운로드 완료 뒤에는 **지도 DB 구축 중**으로 표시합니다. DB 가져오기·색인은 다운로드 이후 추가로 걸리므로 다운로드 예상 시각은 전체 준비 완료 시각이 아닙니다. 전체 소요 시간은 신뢰할 근거가 없어 `계산 불가`로 안내하고, 준비 완료 시 실제 소요 시간과 완료 시각을 출력합니다. 준비 대기 제한 시간(`--nominatim-ready-timeout`)은 완료 예상 시간이 아닙니다.

## 옵션

`--nominatim-docker`를 지정하면 실행 전에 Docker 실행 파일 설치 여부, 데몬 연결·권한, 기존 컨테이너·DB 볼륨의 설정 일치 여부, 포트, 이미지 유무를 터미널에 안내합니다. 기존 DB는 볼륨 존재만으로 완료로 판단하지 않고 PostgreSQL 파일과 `import-finished` 표시를 읽기 전용으로 확인합니다. 이미지가 없으면 먼저 이미지를 내려받은 후 확인합니다.

DB 구축 완료가 확인되면 `기존 DB 및 가져오기 완료 표시 확인 · 재다운로드 없이 시작 가능`을 출력합니다. DB가 없거나 미완료 상태이면 다운로드·최초 구축 필요 여부를 안내합니다. 사전 점검을 통과하면 **`사전 점검이 완료되어 실행 준비가 되었습니다. Nominatim 실행을 시작합니다.`**를 출력합니다. 이 메시지는 사전 조건 점검 완료를 뜻하며, 실제 서비스 준비 완료는 상태 API 검사 후 별도로 출력합니다. 이미 실행 중인 컨테이너는 재사용 메시지를 표시합니다. DB 파일이 손상되었는지까지 이 사전 검사로 보장하지는 않습니다.

```bash
python3 apps/photo_browser/app.py \
  --nominatim-docker \
  --nominatim-image mediagis/nominatim:5.3 \
  --nominatim-volume photo-browser-korea \
  --nominatim-port 8082 \
  --nominatim-ready-timeout 14400
```

다른 지도는 `--nominatim-pbf-url HTTPS주소`로 지정합니다. 여러 지역은 합쳐진 PBF를 제공하는 URL을 사용하세요. 지도 URL·이미지 설정이 달라지면 **새 볼륨 이름**을 사용해야 하며, 기존 볼륨에 데이터를 자동 덮어쓰지 않습니다. 현재 이미지를 기준으로 볼륨 경로가 정해져 있으므로 사용자 지정 이미지도 같은 저장 구조와 환경변수를 지원해야 합니다.

조회 서버는 로컬 IPv4에만 공개합니다. PostgreSQL 5432 포트는 호스트에 공개하지 않습니다. `PHOTO_BROWSER_REVERSE_GEOCODER_URL`이 설정되어 있으면 `--nominatim-port`에 해당하는 `http://127.0.0.1:포트/reverse`와 같아야 합니다.

## 종료와 재시작

- Photo Browser가 시작한 컨테이너만 종료 관리합니다. 종료할 때 컨테이너는 중지·제거하지만 **지도 DB 볼륨은 남깁니다**.
- `Ctrl+C` (`SIGINT`) 또는 `kill -TERM <Photo Browser PID>`로 종료하면 컨테이너 정리가 끝날 때까지 기다린 뒤 Photo Browser가 종료됩니다. 종료 처리 중 반복된 종료 신호는 정리를 중단하지 않습니다.
- Photo Browser를 `SIGKILL`로 종료해도 별도 감시 프로세스가 부모 파이프 종료를 감지하고 Docker에 정리를 요청합니다. Docker 데몬이 응답하지 않으면 정리가 지연될 수 있습니다.
- 같은 설정의 관리 컨테이너가 실행 중이면 준비를 기다린 뒤 재사용합니다. 재사용한 컨테이너는 해당 Photo Browser가 종료하지 않습니다. 원래 실행한 Photo Browser가 종료하면 그 컨테이너는 종료됩니다.
- 종료된 관리 컨테이너가 남아 있으면 컨테이너만 제거 후 같은 볼륨으로 다시 시작합니다. 생성 중인 컨테이너나 다른 설정의 컨테이너는 임의로 제거하지 않습니다.
- 같은 볼륨을 다른 이름의 컨테이너가 사용 중이면 시작을 거부합니다. 여러 개의 독립 서버가 필요하면 볼륨과 포트를 각각 다르게 지정하세요.

가져오기 도중 중단되어 재시작에 실패하면 로그를 확인하고 필요시 새 볼륨으로 구축하세요. 기존 볼륨을 자동 삭제하거나 강제로 초기화하지 않습니다.

## 웹 모니터링

메인 화면의 **Nominatim** 탭에서 Docker 점검, 이미지·지도 다운로드, DB 구축, 서비스 준비 여부, 오류와 최근 로그(최대 200개)를 확인합니다. 탭을 보는 동안 2초마다 갱신하며 수동 새로고침도 지원합니다. 다운로드 용량·속도·예상 시각은 진행 로그에 함께 표시합니다. 웹 상태 조회에 실패하면 이전 정보임을 알립니다. 실행 중에는 서버에서 3초마다 Nominatim 상태 API를 확인합니다.

Nominatim 시작에 실패하거나 준비 제한 시간이 지나도 Photo Browser는 계속 실행되어 오류를 확인할 수 있습니다. 자동 재시작 기능은 제공하지 않으며 원인 해결 후 Photo Browser를 재시작하세요. 준비 완료 전에 스캔하면 위치 이름 조회에 실패할 수 있으므로 준비 완료 후 다시 스캔하세요. 기존 사진·GPS 정보는 유지됩니다. 이 화면은 현재 Photo Browser 실행 세션을 모니터링하며 재시작하면 로그가 초기화됩니다. 기존 Photo Browser 로그인 보호가 상태 API에도 적용됩니다. Docker 옵션 없이 실행하면 비활성 상태를 표시하며 외부 조회 서버를 관리하지 않습니다.

## 점검

통계 아래의 **빈 위치 태그 사진만 스캔**은 먼저 활성 사진을 DB의 유효한 GPS 좌표로 분류합니다. GPS가 없으면 일반 태그 `no_gps`를 DB에 저장하고 위치 조회에서 제외합니다. **GPS가 있고 행정구역 이름(`capture.place.names`)이 없는 사진만** 목록으로 만들어 Nominatim에 조회하며 사진 원본을 다시 읽지 않습니다. 이미 이름이 있는 사진·동영상·비활성 항목은 조회하지 않습니다. 이후 일반 소스 스캔 등으로 GPS가 확인되면 오래된 `no_gps` 태그는 DB 반영 시 자동 제거합니다. 통계의 위치 조회 대상 수도 같은 기준으로 표시합니다. 조회 대상이 0개여도 버튼을 눌러 `no_gps` 분류를 저장할 수 있습니다.

Nominatim 준비가 완료되어야 실행할 수 있습니다. 처리 수·위치 추가 수·GPS 없음으로 제외한 수·no_gps 태그 신규 저장 수·위치 이름 미확인·오류와 현재 파일을 탭에서 확인할 수 있습니다. **중지하고 저장**하면 처리한 결과를 DB에 반영합니다. 완료·중지 후 통계가 자동 갱신되며 다시 실행하면 여전히 이름이 없는 사진만 대상으로 합니다. 작업은 기존 스캔·병합과 중복 실행하지 않고, 사진 원본과 기존 분류·일반 태그는 유지하며 `no_gps` 태그만 GPS 유무에 맞춰 추가·제거합니다. 강제 종료 시 마지막 DB 반영 이후 결과는 다시 처리해야 할 수 있으며 조회 캐시는 재사용합니다.

Nominatim 탭의 **사진·태그 통계**는 현재 DB의 활성 사진을 고유 사진 ID로 집계합니다. 전체 사진 수, 위치·일반 태그를 합친 고유 태그 이름 수, 종류별 태그 수와 태그가 전혀 없는 사진 수·비율을 표시합니다. 동영상·휴지통·등록 해제 항목은 제외합니다. 위치 태그에는 행정구역 이름과 GPS 태그가 포함됩니다.

표에서 위치 태그와 일반 태그를 선택하고, 태그별 사진 수와 전체 사진 대비 비율, 해당 태그가 없는 사진 수·비율을 확인하세요. 한 사진의 중복 태그는 한 번만 세며 여러 태그를 가진 사진은 각 태그에 포함되므로 비율 합계는 100%를 넘을 수 있습니다. 검색과 100개씩 페이지 이동을 지원하고, 탭을 보는 동안 30초마다 갱신합니다. DB 세대가 같으면 집계 결과를 재사용하며 **태그 통계 다시 집계**로 강제 갱신할 수 있습니다. 통계는 Docker 실행 여부와 관계없이 Photo Browser DB에서 읽으며 Nominatim 서버에 조회하지 않습니다.

```bash
docker ps -a --filter label=org.berepi.photo-browser.nominatim=1
docker volume ls
curl --fail 'http://127.0.0.1:8080/status?format=json'
```

컨테이너 이름은 Photo Browser 시작 로그에 출력합니다. 세부 로그는 `docker logs 컨테이너이름`으로 확인하세요. 컨테이너에는 지도 가져오기를 위한 충분한 디스크와 메모리가 필요하며, Docker Desktop 사용 시 VM에 할당된 자원도 확인하세요.

현재 개발 환경에 Docker 실행 파일이 없어 실제 이미지 다운로드·지도 가져오기는 실행하지 않았습니다. Docker CLI 대체 실행기와 별도 서버 프로세스를 사용해 생성 옵션, 정상·강제 종료, 볼륨 보존, 기존 자원 보호를 검증합니다.

스캔·병합의 위치 태그 정책은 동일합니다. 국가 코드 `KR`은 한국어, 그 외는 영어를 요청하며 원본 GPS와 국가 코드를 DB에 저장합니다. 지도 데이터: [© OpenStreetMap 기여자](https://www.openstreetmap.org/copyright).

## Docker 독립 서비스

Photo Browser 없이 지도 다운로드·DB 가져오기·조회 API까지 실행할 수 있습니다. Docker Engine/Desktop과 **Docker Compose v2**, Python 3가 필요합니다. 호스트에 PostgreSQL이나 Nominatim Python 패키지를 설치할 필요는 없습니다. [mediagis 커뮤니티 이미지](https://github.com/mediagis/nominatim-docker)를 사용하며, 기본 지도는 한국, 가져오기 범위는 행정구역·지명 중심, API는 역지오코딩 전용입니다.

저장소 루트에서 실행하세요. 실행기는 다른 작업 디렉토리에서도 자신의 설정 파일을 찾아 사용합니다.

```bash
# .env 생성: 임의의 DB 암호를 생성하고 파일 권한을 0600으로 설정
python3 apps/photo_browser/nominatim/docker_service.py init

# 필요한 경우 nominatim/.env에서 포트·지도 URL·자원 설정을 편집한 뒤 실행
python3 apps/photo_browser/nominatim/docker_service.py up
python3 apps/photo_browser/nominatim/docker_service.py logs
# 로그 보기 종료는 Ctrl+C; 컨테이너는 계속 실행됨
python3 apps/photo_browser/nominatim/docker_service.py check
```

`up`은 백그라운드 실행 요청입니다. 최초 실행은 이미지와 지도 다운로드 및 DB 가져오기에 시간이 걸립니다. `check`가 **지도 DB 준비 완료**를 출력하고 종료 코드 0을 반환해야 조회할 수 있습니다. 가져오기 중에는 준비 검사가 실패하며, 오래 걸리면 Docker health 상태가 `unhealthy`로 표시될 수 있습니다. `logs`로 실제 진행·오류를 확인하세요. Docker health 검사는 HTTP 응답뿐 아니라 Nominatim의 `status: 0`도 확인합니다.

```bash
python3 apps/photo_browser/nominatim/docker_service.py status
python3 apps/photo_browser/nominatim/docker_service.py stop
python3 apps/photo_browser/nominatim/docker_service.py up
python3 apps/photo_browser/nominatim/docker_service.py restart
# 컨테이너·네트워크 제거, 지도 DB 볼륨은 보존
python3 apps/photo_browser/nominatim/docker_service.py down
```

DB는 Compose 프로젝트 `photo-browser-nominatim`의 `map-data` 영구 볼륨에 저장됩니다. `down` 후 `up`, 컨테이너 재생성 시에도 완료된 DB를 재사용합니다. `docker compose down -v`나 볼륨 삭제는 데이터를 지우므로 사용하지 마세요. `.env`만 복사해서는 DB가 옮겨지지 않습니다. Photo Browser의 사진 백업에도 이 Docker 볼륨은 포함되지 않습니다. 가져오기를 중간에 중단한 DB는 정상 완료 DB와 다르므로 로그를 확인하고 복구 여부를 판단해야 합니다.

`.env`는 Git에서 제외되며, `init`을 다시 실행해도 기존 파일을 덮어쓰지 않습니다. 수동 설정은 `.env.example`을 `.env`로 복사한 뒤 `NOMINATIM_PASSWORD`를 충분히 긴 임의 값으로 채우세요. 이 암호는 내부 DB 연결용이며 API 로그인 암호가 아닙니다. 기본 API는 `127.0.0.1:8080`에만 공개하고 PostgreSQL 포트는 공개하지 않습니다. 다른 장치에 공개하려면 별도의 HTTPS·접근 제어를 구성하세요. 이미지 시작 로그와 Docker 관리 권한에도 내부 설정이 노출될 수 있으므로 접근을 제한하세요.

| 설정 | 용도 |
| --- | --- |
| `HTTP_PORT` / `BIND_ADDRESS` | 호스트 API 포트 / 접속 허용 인터페이스 |
| `PBF_URL` | 최초 가져올 HTTPS `.osm.pbf` 주소 |
| `IMPORT_STYLE` | 기본 `admin`, 도로·주소가 필요하면 최초 가져오기 전에 `street` 또는 `address` 선택 |
| `THREADS` / `GUNICORN_WORKERS` | 가져오기 스레드 / API 작업자 수 |
| `SHM_SIZE`, `POSTGRES_*` | 공유 메모리 및 PostgreSQL 메모리 설정 |
| `NOMINATIM_IMAGE` | 기본 `mediagis/nominatim:5.3`; 배포 환경에서는 검증한 이미지 digest로 고정 가능 |

메모리 기본값은 이미지 기본값보다 낮게 잡았습니다. 실제 RAM·SSD 여유 공간은 지도 크기에 따라 달라지며, 이 값이 실행 가능 최소 사양을 보장하지는 않습니다. Docker Desktop의 메모리·디스크 할당도 확인하세요. 호스트 CPU에 대응하는 이미지가 필요합니다. 기존 볼륨에 대해 지도 URL·가져오기 스타일을 바꾸어도 재가져오기는 하지 않으며, 지도 자동 업데이트는 설정하지 않습니다. 별도 지역 DB가 필요하면 다른 Compose 프로젝트 이름(`COMPOSE_PROJECT_NAME`)과 API 포트를 사용하세요. 생성 이후 같은 프로젝트 이름을 유지해야 같은 볼륨을 사용합니다.

직접 Compose로 실행할 수도 있습니다.

```bash
cd apps/photo_browser/nominatim
docker compose --env-file .env -f compose.yaml up -d
docker compose --env-file .env -f compose.yaml ps --all
docker compose --env-file .env -f compose.yaml down
```

Docker 서비스가 준비된 뒤 Photo Browser를 실행하세요. 별도 서비스이므로 `--nominatim-docker`는 지정하지 않습니다. Photo Browser가 종료되어도 Docker 서비스는 계속 실행되며, Docker 재시작 시 `unless-stopped` 정책으로 다시 시작합니다.

```bash
PHOTO_BROWSER_REVERSE_GEOCODER_URL=http://127.0.0.1:8080/reverse \
  python3 apps/photo_browser/app.py
```

다른 서비스가 8080 포트를 사용 중이면 `.env`의 `HTTP_PORT`를 변경하고 위 조회 주소도 같은 포트로 맞추세요. 독립 Compose 서비스의 DB 볼륨은 Photo Browser의 `--nominatim-docker` 볼륨과 별개입니다.

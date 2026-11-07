# Photo Browser용 Nominatim 실행 서비스

이 디렉토리의 코드는 다음 명령 형식으로 실행하는 HTTP 서버입니다.

```bash
nominatim serve --project-dir /srv/nominatim-project --server 127.0.0.1:8080
```

공식 `nominatim-api`의 Falcon ASGI 애플리케이션을 Uvicorn으로 실행합니다. `/status?format=json`과 `/reverse?format=jsonv2&lat=...&lon=...`를 포함한 공식 API를 제공하며, 별도 프로세스로 분리하지 않아 Photo Browser의 종료 감시 기능과 연결됩니다.

## Ubuntu에서 자동 구축

Ubuntu **22.04 / 24.04**에서 일반 사용자로 실행하세요. 전체 스크립트를 `sudo`로 실행하지 않습니다. 시스템 패키지 설치·PostgreSQL 시작·DB 역할 생성에만 내부적으로 `sudo`를 사용합니다. 다른 OS에서는 `--dry-run`만 지원합니다.

```bash
# 실행 계획 확인: 설치·다운로드·DB 변경 없음
python3 apps/photo_browser/nominatim/setup_local.py --dry-run

# 실제 구축: 기본 한국 지도
python3 apps/photo_browser/nominatim/setup_local.py
```

PostgreSQL/PostGIS·osm2pgsql·빌드 의존성을 설치하고, 전용 가상환경에 Nominatim DB/API 5.3.3을 설치합니다. [Geofabrik 한국 지도](https://download.geofabrik.de/asia/south-korea.html)를 내려받아 행정구역 중심(admin), 역지오코딩 전용(reverse-only) DB로 가져옵니다. 공식 DB 검사를 통과하면 완료 기록과 실행 스크립트를 생성합니다.

| 항목 | 기본값 |
| --- | --- |
| 프로젝트·설정 | `~/.local/share/photo-browser/nominatim-project` |
| Python 가상환경 | `~/.local/share/photo-browser/nominatim-venv` |
| PostgreSQL DB | `photo_browser_nominatim` |
| 다운로드 지도 | 프로젝트의 `downloads/map.osm.pbf` |
| 구축 기록 / 실행기 | 프로젝트의 `setup.json` / `start-nominatim.sh` |

지도 DB 파일은 PostgreSQL의 데이터 디렉토리에 저장됩니다. `--project-dir`은 해당 DB 파일의 저장 위치를 변경하지 않습니다. 프로젝트와 PostgreSQL 저장소 각각 기본 10 GiB 여유 공간, 최소 RAM 2 GiB를 검사하며 실제 필요량을 보장하는 수치는 아닙니다.

현재 Linux 사용자와 같은 이름의 PostgreSQL 역할이 없으면 공식 가져오기 절차처럼 superuser 역할을 생성합니다. 새 역할의 권한은 구축 후에도 유지됩니다. 이미 존재하는 역할의 권한, PostgreSQL 설정 파일·인증 규칙, 기존 DB는 변경하거나 삭제하지 않습니다.

다른 지도나 저장 경로를 지정할 수 있습니다. 프로젝트와 가상환경은 실행 사용자가 쓸 수 있는 분리된 경로로 지정하세요.

```bash
python3 apps/photo_browser/nominatim/setup_local.py \
  --project-dir "$HOME/photo-nominatim/project" \
  --venv "$HOME/photo-nominatim/venv" \
  --db-name photo_regions \
  --osm-file /data/maps/region.osm.pbf \
  --threads 2 --osm2pgsql-cache 256
```

`--osm-url HTTPS주소`는 다른 다운로드 범위, `--osm-sha256 검증값`은 파일 검증, `--min-free-gb`는 최소 디스크 여유를 지정합니다. 초기 가져오기만 자동화하며 정기 지도 업데이트는 설정하지 않습니다. 가져온 지도 범위 밖의 위치는 조회할 수 없습니다.

### 구축 후 연결과 재실행

완료 시 출력되는 `--nominatim-command`를 기존 Photo Browser 실행 명령에 추가하세요. 기본 경로 예시는 다음과 같습니다.

```bash
python3 apps/photo_browser/app.py \
  --nominatim-command "$HOME/.local/share/photo-browser/nominatim-project/start-nominatim.sh"
```

조회 서버의 시작·종료는 Photo Browser가 관리합니다. 구축 스크립트 자체는 상시 서버를 실행하거나 systemd 서비스로 등록하지 않습니다.

같은 설정으로 재실행하면 완료된 DB를 검사하고 가져오기는 건너뜁니다. 관리 기록 없는 기존 DB, 중단된 가져오기의 부분 DB, 다른 설정이나 기존 `.env`와 충돌하면 자동 덮어쓰기 없이 중단합니다. 기존 DB를 확인하거나 새 DB 이름과 새 프로젝트로 구축하세요. DB 삭제 옵션은 없습니다.

개발 환경은 macOS이므로 실제 Ubuntu 설치·전체 지도 가져오기는 이 환경에서 실행하지 않았습니다. 설치 흐름·재실행·실패 복구·기존 DB 보호와 dry-run의 무변경 동작은 대체 실행기를 사용한 테스트로 검증합니다.

## 준비

Nominatim 엔진과 OpenStreetMap 지도 DB를 준비한 프로젝트가 필요합니다. `/srv/nominatim-project`는 프로젝트의 `.env` 등 DB 연결 설정을 읽을 위치이며, 빈 폴더만 만들어서는 주소 조회가 되지 않습니다. `server.py`는 지도 DB 가져오기·PostgreSQL 설치를 수행하지 않습니다. 위의 `setup_local.py`로 자동 구축하거나 공식 절차로 준비하세요.

공식 문서:

- [Nominatim 설치와 지도 DB 준비](https://nominatim.org/release-docs/latest/admin/Installation/)
- [Python API 서버 구성](https://nominatim.org/release-docs/latest/admin/Deployment-Python/)

저장소 루트에서, 서버를 실행할 Python 가상환경에 의존성을 설치합니다. `PyICU` 등은 운영체제에 따라 별도 빌드 도구·시스템 라이브러리가 필요할 수 있습니다.

```bash
python3 -m pip install -r apps/photo_browser/nominatim/requirements.txt
```

## 단독 실행

Python 경로를 명시하는 방법:

```bash
python3 apps/photo_browser/nominatim/server.py serve \
  --project-dir /srv/nominatim-project --server 127.0.0.1:8080
```

요청한 `nominatim serve` 명령으로 실행하는 방법:

```bash
export PATH="$PWD/apps/photo_browser/nominatim:$PATH"
nominatim serve --project-dir /srv/nominatim-project --server 127.0.0.1:8080
```

이 PATH 설정은 Photo Browser의 로컬 실행기를 선택합니다. 지도 가져오기 같은 다른 공식 Nominatim 명령은 이 실행기가 지원하지 않으므로 기존 Nominatim 도구의 절대 경로를 사용하세요. `--help`는 의존성 설치 없이도 확인할 수 있습니다.

```bash
curl --fail 'http://127.0.0.1:8080/status?format=json'
curl --get 'http://127.0.0.1:8080/reverse' \
  --data-urlencode 'format=jsonv2' \
  --data-urlencode 'lat=37.511' --data-urlencode 'lon=127.094' \
  --data-urlencode 'accept-language=ko,en'
```

상태 응답의 `status: 0`은 지도 DB를 사용할 수 있다는 뜻입니다. 실제 행정구역은 가져온 지도 데이터와 좌표에 따라 결정됩니다.

## Photo Browser와 함께 실행

저장소 루트에서 실행하며, 프로젝트 경로와 가상환경의 Python 경로는 실제 값으로 바꾸세요.

```bash
python3 apps/photo_browser/app.py \
  --nominatim-command 'python3 apps/photo_browser/nominatim/server.py serve --project-dir /srv/nominatim-project --server 127.0.0.1:8080'
```

또는 다음과 같이 실행합니다. 시스템에서 `nominatim`을 찾지 못하면 Photo Browser가 이 디렉토리의 `server.py`를 자동 선택합니다. Photo Browser를 실행하는 Python 환경에 의존성이 설치되어 있어야 합니다.

```bash
python3 apps/photo_browser/app.py \
  --nominatim-command 'nominatim serve --project-dir /srv/nominatim-project --server 127.0.0.1:8080'
```

기본 조회 주소는 `http://127.0.0.1:8080/reverse`입니다. 포트를 변경한다면 `PHOTO_BROWSER_REVERSE_GEOCODER_URL`도 같은 포트로 설정하세요. Photo Browser는 정상 동작 중인 기존 서버를 재사용하고, 새로 실행한 서버만 정상 종료·강제 종료 시 정리합니다.

지도 데이터: [© OpenStreetMap 기여자](https://www.openstreetmap.org/copyright).

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

지도 가져오기가 끝나고 상태 API의 `status`가 `0`이 되면 Photo Browser 웹서버를 시작합니다. 컨테이너 로그는 실행 터미널에도 표시합니다. 최초 가져오기는 데이터 크기·서버 성능에 따라 오래 걸릴 수 있습니다.

## 옵션

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
- Photo Browser를 `SIGKILL`로 종료해도 별도 감시 프로세스가 부모 파이프 종료를 감지하고 Docker에 정리를 요청합니다. Docker 데몬이 응답하지 않으면 정리가 지연될 수 있습니다.
- 같은 설정의 관리 컨테이너가 실행 중이면 준비를 기다린 뒤 재사용합니다. 재사용한 컨테이너는 해당 Photo Browser가 종료하지 않습니다. 원래 실행한 Photo Browser가 종료하면 그 컨테이너는 종료됩니다.
- 종료된 관리 컨테이너가 남아 있으면 컨테이너만 제거 후 같은 볼륨으로 다시 시작합니다. 생성 중인 컨테이너나 다른 설정의 컨테이너는 임의로 제거하지 않습니다.
- 같은 볼륨을 다른 이름의 컨테이너가 사용 중이면 시작을 거부합니다. 여러 개의 독립 서버가 필요하면 볼륨과 포트를 각각 다르게 지정하세요.

가져오기 도중 중단되어 재시작에 실패하면 로그를 확인하고 필요시 새 볼륨으로 구축하세요. 기존 볼륨을 자동 삭제하거나 강제로 초기화하지 않습니다.

## 점검

```bash
docker ps -a --filter label=org.berepi.photo-browser.nominatim=1
docker volume ls
curl --fail 'http://127.0.0.1:8080/status?format=json'
```

컨테이너 이름은 Photo Browser 시작 로그에 출력합니다. 세부 로그는 `docker logs 컨테이너이름`으로 확인하세요. 컨테이너에는 지도 가져오기를 위한 충분한 디스크와 메모리가 필요하며, Docker Desktop 사용 시 VM에 할당된 자원도 확인하세요.

현재 개발 환경에 Docker 실행 파일이 없어 실제 이미지 다운로드·지도 가져오기는 실행하지 않았습니다. Docker CLI 대체 실행기와 별도 서버 프로세스를 사용해 생성 옵션, 정상·강제 종료, 볼륨 보존, 기존 자원 보호를 검증합니다.

스캔·병합의 위치 태그 정책은 동일합니다. 국가 코드 `KR`은 한국어, 그 외는 영어를 요청하며 원본 GPS와 국가 코드를 DB에 저장합니다. 지도 데이터: [© OpenStreetMap 기여자](https://www.openstreetmap.org/copyright).

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

```bash
docker ps -a --filter label=org.berepi.photo-browser.nominatim=1
docker volume ls
curl --fail 'http://127.0.0.1:8080/status?format=json'
```

컨테이너 이름은 Photo Browser 시작 로그에 출력합니다. 세부 로그는 `docker logs 컨테이너이름`으로 확인하세요. 컨테이너에는 지도 가져오기를 위한 충분한 디스크와 메모리가 필요하며, Docker Desktop 사용 시 VM에 할당된 자원도 확인하세요.

현재 개발 환경에 Docker 실행 파일이 없어 실제 이미지 다운로드·지도 가져오기는 실행하지 않았습니다. Docker CLI 대체 실행기와 별도 서버 프로세스를 사용해 생성 옵션, 정상·강제 종료, 볼륨 보존, 기존 자원 보호를 검증합니다.

스캔·병합의 위치 태그 정책은 동일합니다. 국가 코드 `KR`은 한국어, 그 외는 영어를 요청하며 원본 GPS와 국가 코드를 DB에 저장합니다. 지도 데이터: [© OpenStreetMap 기여자](https://www.openstreetmap.org/copyright).

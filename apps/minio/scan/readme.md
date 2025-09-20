# MinIO CSV 스캐너

이 유틸리티는 MinIO 객체 스토리지에 연결해 버킷에 들어 있는 CSV 파일을 탐색하고 관리할 수 있는 도구를 제공합니다. Streamlit 기반의 웹 UI와 명령줄 인터페이스(CLI) 두 가지 실행 방식을 지원하므로, 상황에 맞는 워크플로를 선택해 사용할 수 있습니다.

## 주요 기능

- **자동 의존성 부트스트랩** – 스크립트는 `pandas`, `streamlit`, `minio` 패키지가 설치되어 있는지 확인하고, 누락된 패키지가 있을 경우 먼저 설치를 진행합니다. 감지된 가상환경 경로(`~/devel_opemnt/venv/bin`)도 함께 출력해 실행 컨텍스트를 확인할 수 있습니다.【F:apps/minio/scan/main.py†L12-L43】
- **설정 템플릿 생성** – 연결 정보는 동일 디렉터리에 위치한 `nocommit_minio.json`에서 불러옵니다. 파일이 없으면 기본 필드(`endpoint`, `access_key`, `secret_key`, `secure`)와 함께 사용자 지정 TLS용 `ssl` 블록(인증서 경로와 검증 여부 설정 포함)이 채워진 템플릿을 자동으로 생성하고, 콘솔과 Streamlit UI 모두에 안내를 제공합니다.【F:apps/minio/scan/main.py†L309-L366】
- **Streamlit 대시보드** – `streamlit run`으로 실행하면 CSV 필드 목록, 특정 필드의 누락 값 통계(비율 포함), 특정 필드를 제거한 복사본 만들기 기능이 탭 형태로 제공됩니다. 스캔 중에는 진행률 바와 “현재/전체” 파일 수가 함께 표시됩니다.【F:apps/minio/scan/main.py†L369-L475】
- **CLI 대응 기능** – 모듈을 직접 실행하면 `list`, `stats`, `copy` 명령을 제공하여 UI와 동일한 작업을 SSH나 자동화 환경에서도 수행할 수 있습니다. CLI 모드에서도 사용 중인 MinIO 연결 정보가 출력됩니다.【F:apps/minio/scan/main.py†L478-L594】
- **디렉터리 감사 기록** – 각 스캔 시 접근한 고유 디렉터리를 `scanned_dirs.txt`에 기록하여, 최근에 처리된 경로를 손쉽게 추적할 수 있습니다.【F:apps/minio/scan/main.py†L185-L206】【F:apps/minio/scan/main.py†L234-L259】

## 설정 방법

1. `apps/minio/scan/` 디렉터리로 이동합니다.
2. Streamlit 또는 CLI 방식으로 스크립트를 한 번 실행합니다. `nocommit_minio.json`이 없으면 템플릿이 자동으로 생성됩니다.
3. 생성된 `nocommit_minio.json`을 열어 MinIO `endpoint`, `access_key`, `secret_key` 값을 입력하고, HTTPS를 사용하는 경우 `"secure": true`로 변경합니다. 사설 CA 사용이나 클라이언트 인증서가 필요하다면 `ssl` 블록을 활성화(`"enabled": true`)하고 `ca_file`·`cert_file`·`key_file` 경로 또는 `cert_check` 옵션을 원하는 값으로 조정합니다.【F:apps/minio/scan/main.py†L309-L366】

## Streamlit UI 실행

```bash
streamlit run apps/minio/scan/main.py
```

인터페이스는 연결 정보와 자동 설치된 패키지 목록을 보여주며, 다음 세 가지 탭을 제공합니다:

1. **List fields** – 버킷과 선택적 경로(prefix)를 입력하면 각 CSV 객체와 해당 컬럼 이름을 나열합니다.
2. **Field stats** – 버킷, 경로, 컬럼 이름을 지정하면 일치하는 모든 CSV에서 총 행 수와 누락(NaN/None) 수, 누락 비율을 계산합니다.
3. **Copy without field** – 원본 버킷/객체와 제거할 컬럼, 대상 객체(필요 시 다른 버킷)를 입력하면 지정한 컬럼이 제외된 복사본을 생성합니다.【F:apps/minio/scan/main.py†L369-L475】

각 탭은 CSV를 순회하는 동안 진행 상황을 갱신하며, 스캔이 끝날 때마다 같은 폴더에 `scanned_dirs.txt`를 업데이트하여 처리한 디렉터리를 기록합니다.【F:apps/minio/scan/main.py†L185-L206】【F:apps/minio/scan/main.py†L234-L259】

## CLI 사용법

모듈을 파이썬으로 직접 실행하면 UI와 동일한 기능을 제공하는 하위 명령을 사용할 수 있습니다:

```bash
python apps/minio/scan/main.py list <bucket> [prefix]
python apps/minio/scan/main.py stats <bucket> <field> [prefix]
python apps/minio/scan/main.py copy <src_bucket> <src_object> <field> <dest_object> [--dest-bucket <bucket>]
```

- `list`는 각 CSV 경로와 필드 이름을 쉼표로 구분해 출력합니다.
- `stats`는 지정한 필드의 전체 행 수와 누락 값을 집계하고, 누락 비율도 함께 보여줍니다.
- `copy`는 지정한 필드를 제거한 CSV 복사본을 새 객체(필요 시 다른 버킷)로 저장하며, 변경 전후의 컬럼 목록을 출력합니다.【F:apps/minio/scan/main.py†L478-L594】

모든 명령은 실행 시 설정을 검증하고, 필요한 의존성을 설치하며, 사용 중인 MinIO 연결 정보(HTTPS 여부, 인증서 검증 상태, 지정한 SSL 경로)를 로그로 출력하고, 작업하면서 `scanned_dirs.txt`를 최신 상태로 유지합니다.【F:apps/minio/scan/main.py†L12-L43】【F:apps/minio/scan/main.py†L309-L366】【F:apps/minio/scan/main.py†L384-L403】【F:apps/minio/scan/main.py†L539-L594】

## 출력 산출물

- `scanned_dirs.txt` – 각 스캔 후 접근한 고유 디렉터리를 기록하는 파일로, 최근 분석 내역을 감사할 때 유용합니다.【F:apps/minio/scan/main.py†L185-L206】【F:apps/minio/scan/main.py†L234-L259】
- 콘솔/Streamlit 로그 – 의존성 설치 여부와 MinIO 연결 정보를 표시해 실행 환경을 확인할 수 있습니다.【F:apps/minio/scan/main.py†L12-L43】【F:apps/minio/scan/main.py†L384-L403】【F:apps/minio/scan/main.py†L539-L594】

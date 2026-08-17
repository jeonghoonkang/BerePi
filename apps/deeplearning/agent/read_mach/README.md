# read_mach

## 외부 LLM·서브 에이전트용 기준 프롬프트

외부 LLM이나 서브 에이전트에게 `read_mach`의 실행 방법, 주요 구조 또는 장애 원인
분석을 요청할 때는 아래 프롬프트를 복사해 사용합니다. 기준 소스는 GitHub의
`https://github.com/jeonghoonkang/BerePi/tree/master/apps/deeplearning/agent/read_mach`이며,
외부 LLM이 해당 URL을 열 수 없다면 디렉토리의 파일을 함께 제공합니다.

```text
당신은 Python 문서·이미지 문자 추출 모듈인 read_mach의 기술 분석가이자 실행
가이드 작성자다. 추측하지 말고 아래 GitHub URL의 실제 코드와 README를 근거로
현재 구현을 분석하라.

https://github.com/jeonghoonkang/BerePi/tree/master/apps/deeplearning/agent/read_mach

[목표]
1. 처음 사용하는 사람이 read_mach를 설치하고 안전하게 실행할 수 있게 안내한다.
2. 통합 진입점부터 형식별 추출기, 로컬 XML/텍스트 추출, 외부 비전 LLM 호출,
   결과 저장까지의 주요 구조와 데이터 흐름을 설명한다.
3. 기본 LLM Routing 서버와 Cloud Fast Track 경로가 어떤 조건에서 선택되는지
   코드 근거로 확인한다.
4. 실행 실패나 장시간 대기 시 확인할 진단 절차를 제시한다.

[반드시 확인할 파일]
- README.md: 지원 기능, 설치, 설정 및 사용 예시
- text_extract.py: 통합 CLI, 입력 탐색, 확장자별 디스패치
- vision_ocr_support.py: 공용 이미지 OCR, 인증, 서버 URL 선택
- config/server_config.json: 서버·모델·타임아웃 설정 스키마
- pdf_text_extractor.py: PDF 텍스트 레이어, 페이지 OCR 및 진행률
- pptx_text_extractor.py: PPTX 슬라이드 문자, 포함 이미지 OCR 및 진행률
- docx_text_extractor.py, hwpx_text_extractor.py: 패키지 XML과 포함 이미지 처리
- image_text_extractor.py, jpg_text_extractor.py, png_text_extractor.py: 이미지 OCR
- url_text_extractor.py: 외부 LLM을 사용하지 않는 웹 본문 추출
- bizcard_text_extractor.py: 로컬/WebDAV 명함 OCR과 상태 저장
- requirements.txt와 test_*.py: 의존성과 검증 가능한 동작

[분석 규칙]
- 파일명, 함수명, CLI 옵션과 설정 키는 실제 코드에 존재하는 것만 사용한다.
- 코드의 현재 동작과 개선 제안을 명확히 구분한다.
- 비밀번호, 토큰, 실제 운영 서버 주소를 출력하거나 소스·README·설정 파일에
  저장하지 않는다. 비밀값은 password_env가 지정한 환경변수의 자리표시자로만 쓴다.
- 입력 파일은 read_mach/input 내부에 있어야 한다는 경로 제한을 확인한다.
- OCR이 필요 없는 문서 텍스트 추출과 외부 LLM 호출이 필요한 작업을 구분한다.
- PPTX의 --skip-embedded-image-ocr, PDF/PPTX 페이지 범위, --fail-fast와 진행률 출력의
  의미를 설명한다.
- --cloud-fast-track을 선택하지 않으면 server_url, 선택하면
  --cloud-fast-track-url 또는 cloud_fast_track_url을 사용하는지 확인한다.
- Cloud Fast Track은 cloud_fast_track_url을 베이스 주소로 사용해
  /api/gcp/status를 확인하고 /api/gcp/generate로 요청하는지 확인한다.
- 명령을 실행하기 전 --help, 설정 파일 존재 여부, 의존성 설치 여부와 입력 파일
  존재 여부를 먼저 확인한다.
- 실제 네트워크 호출이나 파일 변경을 요청받지 않았다면 분석과 명령 제안까지만 한다.

[결과 형식]
다음 순서로 한국어 보고서를 작성한다.
1. 한 문단 요약
2. 주요 구조: 파일/역할 표와 입력→디스패치→추출→선택적 OCR→출력 흐름
3. 설치 및 사전 조건: Linux/macOS와 Windows PowerShell 명령
4. 설정 키 표: server_url, cloud_fast_track_url, model, target_id,
   timeout_seconds, password_env
5. 대표 실행 명령:
   - 자동 탐색
   - 파일 하나 또는 여러 개
   - PDF 페이지 범위
   - PPTX 페이지 범위
   - PPTX 전체 OCR
   - PPTX 이미지 OCR 제외
   - 기본 server_url 사용
   - Cloud Fast Track 설정값 사용
   - Cloud Fast Track 주소를 CLI에서 일시 지정
   - URL 본문 및 명함 처리
6. 출력 파일과 메타데이터 설명
7. 진행률이 멈춘 것처럼 보일 때의 확인 순서
8. 테스트 및 검증 명령
9. 코드에서 확인되지 않았거나 사용자에게 받아야 하는 값

명령에는 실제 비밀번호 대신 <READ_MACH_PASSWORD>, 실제 서버 주소 대신
<SERVER_URL> 또는 <CLOUD_FAST_TRACK_URL>, 입력 파일 대신 <INPUT_FILE>을 사용하라.
근거가 부족한 내용은 단정하지 말고 확인이 필요한 파일이나 질문을 명시하라.
```

## 추가 문서 및 그림 입력

### 명함 OCR 문서 생성

`--bizcard`는 JPG/PNG 명함을 모델 서버로 전송해 OCR하고 성명, 회사, 부서, 직책,
전화번호, 이메일, 주소 등을 구조화합니다. `output/bizcards.md` 한 파일의 위쪽에
명함 Index를 만들고, 그 아래에 각 명함 내용을 연속해서 저장합니다.

로컬 명함은 `input` 디렉토리 내부 파일을 지정합니다. 여러 장은 `--input-file`을
반복해서 전달할 수 있고, 파일을 생략하면 `input` 아래의 모든 JPG/JPEG/PNG를 처리합니다.

```powershell
$env:READ_MACH_PASSWORD = "<모델 서버 비밀번호>"
python .\text_extract.py --bizcard `
  --input-file ".\input\card-front.jpg" `
  --input-file ".\input\card-back.png"
```

WebDAV 폴더의 명함을 처리하려면 다음 환경변수와 `--bizcard-webdav`를 사용합니다.
인증이 필요 없는 WebDAV라면 사용자명과 비밀번호를 생략할 수 있습니다.

```powershell
$env:READ_MACH_WEBDAV_USERNAME = "<WebDAV 사용자명>"
$env:READ_MACH_WEBDAV_PASSWORD = "<WebDAV 앱 비밀번호>"
python .\text_extract.py --bizcard --bizcard-webdav
```

WebDAV에서 내려받은 명함 원본을 OCR 처리와 함께 로컬 디렉토리에도 저장하려면
`--webdav-save-dir`을 지정합니다. 저장 디렉토리가 없으면 자동으로 생성됩니다.

```powershell
python .\text_extract.py --bizcard --bizcard-webdav `
  --webdav-save-dir ".\input\webdav"
```

같은 다운로드에 동일한 파일명이 여러 개 있으면 `_2`, `_3` 접미사를 붙여 모두
보존합니다. 이후 같은 명령을 다시 실행하면 같은 이름의 로컬 파일은 최신 원격
내용으로 갱신됩니다.

기본 WebDAV 주소:

```text
http://***.org:111/apps/memories/folders/Photos/memories/biz_card
```

다른 주소를 사용하려면 `--webdav-url`로 변경할 수 있습니다. WebDAV 모드는 폴더에
`PROPFIND Depth: 1`을 요청하고 JPG/JPEG/PNG 항목을 순차 다운로드합니다.

처리 완료한 명함의 원본 경로 또는 WebDAV URL은 `output/.bizcard_state.json`에
기록됩니다. 다음 실행에서 경로가 같은 명함은 모델에 다시 보내지 않고 건너뜁니다.
이미 처리한 명함을 강제로 다시 읽고 통합 문서의 해당 내용을 갱신하려면 다음과 같이
`--bizcard-force`를 사용합니다.

```powershell
python .\text_extract.py --bizcard --bizcard-webdav --bizcard-force
```

모든 지원 형식의 통합 진입점은 `text_extract.py`입니다. `--input-file`을 생략하면
`input`과 하위 디렉토리에서 PDF, DOCX, PPTX, HWPX, JPG, PNG를 찾아 경로순으로 처리합니다.

```powershell
python .\text_extract.py
```

일부 파일만 순서대로 처리하려면 옵션을 여러 번 지정합니다.

```powershell
python .\text_extract.py `
  --input-file ".\input\보고서.pdf" `
  --input-file ".\input\문서.hwpx" `
  --input-file ".\input\화면.png"
```

여러 웹페이지의 본문을 순차 추출하려면 `--url`을 반복 지정합니다. URL만 지정하면
`input` 디렉토리의 파일은 자동 탐색하지 않습니다.

```powershell
python .\text_extract.py `
  --url "https://example.com/article-1" `
  --url "https://example.com/article-2" `
  --url-timeout 60
```

`--input-file`과 `--url`을 함께 사용하면 지정한 로컬 파일을 먼저 처리한 뒤 URL을
입력 순서대로 처리합니다. 각 URL 결과는 기존과 같이 `output`에 고유 해시가 포함된
`.txt` 본문과 `.json` 메타데이터로 저장됩니다.

기본적으로 한 파일이 실패해도 다음 파일을 계속 처리합니다. 첫 실패에서 중단하려면
`--fail-fast`를 사용합니다. PDF/PPTX 페이지 범위와 PDF 전용 OCR 옵션도 통합
진입점에서 전달할 수 있습니다. PDF와 PPTX를 추출할 때는 전체 페이지 수, 현재
페이지와 진행률이 표시됩니다. 각 입력의 완료·실패 시 소요 시간과 전체 실행 시간은
`시:분:초` 형식으로 출력됩니다.

`input` 디렉토리 안의 DOCX, PPTX, HWPX, JPG, PNG 파일도 각각의 실행 파일로 처리할 수 있습니다.
DOCX/PPTX/HWPX는 XML 본문을 직접 추출하고 문서에 포함된 PNG/JPEG 그림은 비전 모델 OCR로
전사합니다. JPG/PNG는 그림 전체를 비전 모델로 전사합니다. 결과는 `output` 디렉토리에
UTF-8 `.txt` 본문과 `.json` 메타데이터로 저장됩니다.

DOCX/PPTX/HWPX에서 추출한 PNG/JPEG 원본은 지정한 출력 디렉토리 아래
`extract_image/<문서명_형식>`에 저장됩니다. 문서별 디렉토리와 순번 접두사를 사용하므로
서로 다른 문서나 같은 이름의 포함 그림이 덮어쓰이지 않습니다.

```powershell
python .\text_extract.py --input-file ".\input\발표자료.pptx" `
  --output-dir ".\output"
```

OCR에는 포함 그림을 사용하되 디스크에 남기지 않으려면 `--rm-image`를 지정합니다.
같은 출력 디렉토리에 이전 실행에서 남아 있던 해당 문서의 그림 디렉토리도 제거하며,
다른 문서의 `extract_image` 디렉토리는 보존합니다.

```powershell
python .\text_extract.py --input-file ".\input\발표자료.pptx" `
  --output-dir ".\output" --rm-image
```

```powershell
python .\docx_text_extractor.py --input-file ".\input\문서.docx"
python .\pptx_text_extractor.py --input-file ".\input\발표자료.pptx"
python .\hwpx_text_extractor.py --input-file ".\input\문서.hwpx"
python .\jpg_text_extractor.py  --input-file ".\input\사진.jpg"
python .\png_text_extractor.py  --input-file ".\input\화면.png"
```

PPTX에 포함된 이미지가 많으면 이미지별 모델 OCR에 시간이 오래 걸릴 수 있습니다.
`--cloud-fast-track`을 사용하지 않는 로컬 LLM 경로에서는 이미지 OCR 전에
`server_url/api/status`를 확인합니다. 요청 모델을 처리할 수 있는 가용 GPU 수의
50%(`소수점 이하 버림, 최소 1`)만큼 병렬 실행하며, 모델 수는 상태 정보로만
표시하고 병렬도 계산에는 사용하지 않습니다. 각 작업은 GPU별 대표 target에
순서대로 분산합니다. 실행 시 계산 결과가 다음 형식으로 표시됩니다.

```text
[로컬 LLM 병렬 설정] 가용 GPU 4개 | 가용 모델 7개 | GPU 50% 기준 병렬 2개
```

로컬 GPU 요청이 타임아웃, 연결 오류, 서버 오류 또는 모델 응답 오류로 실패하면
동일한 이미지와 프롬프트를 실패한 GPU가 아닌 다음 가용 GPU target으로 재전송합니다.
모든 GPU가 실패하면 시도한 target별 오류를 모아 실행을 실패 처리합니다. 인증 실패처럼
GPU 변경으로 해결할 수 없는 HTTP 4xx 오류는 즉시 중단합니다. 이 동작은
`error_handling/gpu_failover.py`에서 독립적으로 관리합니다.

Cloud Fast Track은 이 로컬 병렬도 계산을 적용하지 않고 기존 전용 GCP 경로를
사용합니다.

슬라이드의 텍스트 상자와 표 문자만 빠르게 추출하려면 다음 옵션을 사용합니다.

```powershell
python .\text_extract.py --input-file ".\input\발표자료.pptx" --skip-embedded-image-ocr
```

PPTX의 일부 슬라이드만 처리하려면 1부터 시작하는 페이지 범위를 지정합니다. 선택한
슬라이드의 문자와 해당 슬라이드가 직접 참조하는 PNG/JPEG만 추출하며, 결과 파일명에는
`pages_<시작>-<끝>` 범위가 포함됩니다.

```powershell
python .\text_extract.py --input-file ".\input\발표자료.pptx" `
  --start-page 3 --end-page 3
```

그림 OCR 또는 포함 그림 OCR이 필요한 경우 PDF 처리와 마찬가지로 서버 비밀번호를 먼저
지정해야 합니다.

```powershell
$env:READ_MACH_PASSWORD = "<서버 비밀번호 입력>"
```

DOCX/PPTX/HWPX에 텍스트만 있고 지원되는 포함 그림이 없으면 모델 서버를 호출하지 않습니다.
현재 문서 내 포함 그림 OCR은 PNG, JPG/JPEG에 적용되며 EMF/WMF 같은 벡터 그림은
건너뜁니다.

## PDF 문자 추출 모듈

`pdf_text_extractor.py`는 PDF의 텍스트 레이어를 페이지별로 읽고, 문자가
부족한 스캔 페이지를 PNG로 렌더링하여 비전 모델 OCR 콜백으로 전달합니다.
`writing_mach --tech-report`도 이 공용 모듈을 사용합니다. 따라서 PDF 읽기,
문자 정규화, 텍스트/OCR 병합 로직은 `read_mach`에서 관리합니다.

주요 진입점:

```python
from read_mach.pdf_text_extractor import extract_pdf_content
```

호출자는 `model_call`과 `progress` 콜백을 제공하여 사용하는 모델 라우터와
로그 방식을 선택할 수 있습니다. Tesseract는 사용하지 않습니다.

`input` 디렉토리의 PDF를 한 페이지씩 이미지로 변환하고 원격 Gemma 비전 모델로
판정합니다. 사진, 삽화, 지도, 스크린샷, 차트, 그래프, 다이어그램 또는 도면이 있는
페이지는 `output` 디렉토리에 PNG로 저장합니다.

결과 파일명 예:

```text
스위스_최종보고서_최종_날인_증빙_page_0001.png
```

## 설치

```bash
cd /path/to/BerePi/apps/deeplearning/agent/read_mach
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Windows PowerShell에서는 가상환경 활성화 명령이 다음과 같습니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

## 서버 설정 파일

기본 서버 설정은 `config/server_config.json`에서 수정합니다.

```json
{
  "server_url": "http://llm-server.example:4004",
  "cloud_fast_track_url": "https://fast-track.example.com",
  "model": "gemma4:31b",
  "target_id": "",
  "timeout_seconds": 240,
  "password_env": "READ_MACH_PASSWORD"
}
```

`server_url`을 실제 LLM Routing 서버 주소로 변경하세요. Cloud Fast Track을 사용할
경우 `cloud_fast_track_url`에 해당 서비스 주소를 입력합니다. 비밀번호 값은 JSON에
기록하지 않고 `password_env`가 가리키는 환경변수에 입력합니다. 다른 설정
파일을 사용하려면 `--config`로 지정합니다.

```bash
python3 extract_picture_pages.py --config ./config/my_server.json
```

실행 시 `--cloud-fast-track`을 선택하면 `cloud_fast_track_url`을 베이스 주소로
사용합니다. 먼저 `<cloud_fast_track_url>/api/gcp/status`를 확인하고, 생성 요청은
`<cloud_fast_track_url>/api/gcp/generate`로 전송합니다. 설정값에는 `/api/gcp/...`
경로를 붙이지 않습니다.

```bash
python3 text_extract.py --input-file ./input/발표자료.pptx \
  --config ./config/my_server.json --cloud-fast-track
```

설정 파일을 수정하지 않고 이번 실행에만 주소를 지정할 수도 있습니다.

```bash
python3 text_extract.py --input-file ./input/발표자료.pptx \
  --cloud-fast-track \
  --cloud-fast-track-url "https://fast-track.example.com"
```

## 실행

Linux/macOS:

```bash
export READ_MACH_PASSWORD="<서버 비밀번호 입력>"
python3 extract_picture_pages.py
```

또는 비밀번호 환경변수를 현재 실행에만 적용할 수 있습니다.

```bash
READ_MACH_PASSWORD="<서버 비밀번호 입력>" python3 extract_picture_pages.py
```

Windows PowerShell:

```powershell
$env:READ_MACH_PASSWORD = "<서버 비밀번호 입력>"
python .\extract_picture_pages.py
```

`input` 디렉토리의 PDF 한 개만 선택하려면 `--input-file`에 파일명을 지정합니다.

```bash
READ_MACH_PASSWORD="<서버 비밀번호 입력>" python3 extract_picture_pages.py \
  --input-file "선택할문서.pdf"
```

경로로 지정할 때도 파일은 `input` 디렉토리 내부에 있어야 합니다.

```powershell
python .\extract_picture_pages.py --input-file ".\input\선택할문서.pdf"
```

`--input-file`을 생략하면 기존과 같이 `input` 디렉토리의 모든 PDF를 처리합니다.

PDF에서 문자와 문장을 추출하려면 `pdf_text_extractor.py`를 실행합니다. 아래 예시는
선택한 PDF의 4~6페이지만 처리하여 `output` 디렉토리에 `.txt` 원문과 `.json`
추출 정보를 저장합니다.

```bash
READ_MACH_PASSWORD="<서버 비밀번호 입력>" python3 pdf_text_extractor.py \
  --input-file ./input/input_sample.pdf \
  --config ./config/this_server_config.json \
  --start-page 4 \
  --end-page 6
```

### URL 웹페이지 문자 추출

웹 URL의 제목과 본문을 문자로 저장하려면 `url_text_extractor.py`를 실행합니다.
HTTP/HTTPS 페이지의 `article`, `main` 또는 본문 영역에서 제목, 문단, 목록,
인용문과 표를 추출하고 메뉴, 스크립트, 폼 등의 불필요한 요소를 제거합니다.

```bash
python3 url_text_extractor.py --url \
  "https://tech.ktcloud.com/entry/2026-03-ktcloud-physical-ai-datacenter-%EC%9D%B8%ED%94%84%EB%9D%BC-%EC%A0%84%EB%A7%9D" \
  --config ./config/this_server_config.json
```

기본 결과는 `output` 디렉토리에 저장됩니다.

- `url_<페이지명>_<hash>.txt`: 정리된 제목과 본문
- `url_<페이지명>_<hash>.json`: 원본 URL, 최종 URL, 제목, 문자 수와 수집 시간

출력 디렉토리와 요청 제한 시간을 변경할 수도 있습니다.

```bash
python3 url_text_extractor.py \
  --url "https://example.com/article" \
  --config ./config/this_server_config.json \
  --output-dir ./output \
  --timeout 60
```

URL 추출에는 모델 서버 설정이나 비밀번호가 필요하지 않습니다. 페이지가 로그인,
JavaScript 렌더링 또는 봇 차단을 요구하면 정적 HTML에서 본문을 추출하지 못할 수
있습니다.

PDF 이미지 판정 및 모델 OCR 실행 전에는 `READ_MACH_PASSWORD`에 모델 서버의 실제
비밀번호를 입력해야 합니다.
비밀번호를 README나 소스 코드에 직접 저장하지 마세요.

기본 설정:

- 입력: `read_mach/input`
- 출력: `read_mach/output`
- 서버: `http://llm-server.example:4004/api/generate`
- 모델: `gemma4:31b`
- 렌더링: 144 DPI

서버의 `/api/status`에서 이미지 입력을 처리할 수 있는 `ollama` 또는 `vllm` 형식
target을 자동으로 선택합니다. Ollama에는 `images` 배열을 전송하고, vLLM에는
OpenAI 호환 멀티모달 `messages`의 `image_url` data URL로 이미지를 전송합니다.
특정 target을 사용하려면 `--target-id TARGET_ID` 또는 `READ_MACH_TARGET_ID`를
지정합니다. 일반 `openai` 형식 target은 자동 선택하지 않습니다.

처음에는 일부 페이지만 시험하는 것을 권장합니다.

```powershell
python .\extract_picture_pages.py --start-page 1 --end-page 5
```

전체 옵션:

```powershell
python .\extract_picture_pages.py --help
```

다른 서버나 모델은 환경변수 또는 옵션으로 변경할 수 있습니다.

```powershell
$env:READ_MACH_SERVER_URL = "http://llm-server.example:4004"
$env:READ_MACH_MODEL = "gemma4:31b"
python .\extract_picture_pages.py --dpi 180 --overwrite
```

모델에는 판정을 위해 각 페이지 이미지가 전송됩니다. 원본 PDF 자체는 전송하지
않습니다. `--dry-run`을 사용하면 판정만 수행하고 PNG를 저장하지 않습니다.

target 자동 선택 시 `/api/status`에서 `dispatch_eligible=true`이고
`available_targets>0`인 Ollama/vLLM target만 사용합니다. 처리 도중 target unavailable
응답을 받으면 상태를 다시 조회하고, 실패한 target을 제외한 다른 가용 target으로
현재 페이지를 한 번 다시 전송합니다.

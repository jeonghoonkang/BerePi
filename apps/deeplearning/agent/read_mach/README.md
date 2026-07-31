# read_mach

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
  "model": "gemma4:31b",
  "target_id": "",
  "timeout_seconds": 240,
  "password_env": "READ_MACH_PASSWORD"
}
```

`server_url`을 실제 LLM Routing 서버 주소로 변경하세요. 비밀번호 값은 JSON에
기록하지 않고 `password_env`가 가리키는 환경변수에 입력합니다. 다른 설정
파일을 사용하려면 `--config`로 지정합니다.

```bash
python3 extract_picture_pages.py --config ./config/my_server.json
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

실행 전 `READ_MACH_PASSWORD`에 모델 서버의 실제 비밀번호를 입력해야 합니다.
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

# read_mach

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

## 실행

Linux/macOS:

```bash
export READ_MACH_PASSWORD="aimodel"
python3 extract_picture_pages.py
```

Windows PowerShell:

```powershell
$env:READ_MACH_PASSWORD = "aimodel"
python .\extract_picture_pages.py
```

기본 설정:

- 입력: `read_mach/input`
- 출력: `read_mach/output`
- 서버: `http://keties.iptime.org:4004/api/generate`
- 모델: `gemma4:31b`
- 렌더링: 144 DPI

서버의 `/api/status`에서 이미지 배열을 그대로 전달할 수 있는 `ollama` 형식 target을
자동으로 선택합니다. 특정 target을 사용하려면 `--target-id TARGET_ID` 또는
`READ_MACH_TARGET_ID`를 지정합니다. OpenAI 형식 target은 현재 라우팅 서버가
`images` 필드를 전달하지 않으므로 선택하지 않습니다.

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
$env:READ_MACH_SERVER_URL = "http://keties.iptime.org:4004"
$env:READ_MACH_MODEL = "gemma4:31b"
python .\extract_picture_pages.py --dpi 180 --overwrite
```

모델에는 판정을 위해 각 페이지 이미지가 전송됩니다. 원본 PDF 자체는 전송하지
않습니다. `--dry-run`을 사용하면 판정만 수행하고 PNG를 저장하지 않습니다.

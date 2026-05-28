# Gemma OCR Client

클립보드 이미지 또는 업로드한 이미지 파일을 Gemma/Ollama 호환 파운데이션 모델에 전송하여 OCR을 수행하는 웹 클라이언트

## 구성

- `client_service.py`: 로컬 웹 서버, 설정 저장, 원격 모델 API 프록시, WebDAV 이미지 다운로드 프록시
- `web/index.html`: OCR 클라이언트 화면
- `web/app.js`: 이미지 업로드, 클립보드 처리, WebDAV 이미지 연동, OCR/YOLO Detection 요청, 결과 및 박스 플롯 표시
- `web/styles.css`: UI 스타일
- `config/client_config.sample.json`: 기본 설정 샘플
- `data/client_config.json`: 실행 시 자동 생성되는 실제 설정 파일
- `data/ocr_history.json`: OCR 결과 히스토리
- `data/webdav_history.json`: WebDAV 연결 설정 히스토리
- `data/result_webdav_history.json`: OCR 결과 저장용 WebDAV 경로 히스토리
- `spec.md`: 실행 흐름 및 함수/API 인터페이스 사양서 (신규 생성)

## 실행 방법

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/camera/ocr/gemma_ocr_client
# Python 3으로 실행
python ./client_service.py
```

브라우저에서 아래 주소를 엽니다.
```text
http://127.0.0.1:8775
```

포트는 환경 변수로 변경할 수 있습니다.
```bash
export GEMMA_OCR_CLIENT_PORT="8780"
python ./client_service.py
```

## 사용 방법

1. 좌측 **Gemma 연결** 패널에서 모델 서버 정보(예: `http://keti-ev1.iptime.org:8082`)를 입력합니다.
2. **연결 확인**을 눌러 `/api/status` 응답을 확인합니다.
3. **설정 저장**을 눌러 현재 설정을 `data/client_config.json`에 저장합니다.
4. 이미지 파일을 드래그 앤 드롭하거나 클릭해서 선택합니다.
5. 클립보드 이미지는 **클립보드 이미지** 버튼 또는 단축키 **Ctrl+V**로 추가합니다.
6. WebDAV 이미지는 좌측 **WebDAV 이미지** 패널의 **주소 1** 또는 **주소 2** 탭에 이미지 URL, User, Password를 입력하고 **이미지 경로 확인** 또는 **WebDAV 경로 불러오기**를 누릅니다.
7. **이미지 전송 확인**으로 선택 이미지가 서버까지 정상 도착하는지 테스트합니다. (모델 추론은 실행하지 않고 전송 테스트만 진행)
8. 필요한 경우 **OCR 프롬프트**를 수정합니다.
9. **OCR 실행**을 눌러 텍스트 추출 결과를 확인합니다.

## YOLO Detection

좌측 **모델 프롬프트** 패널에는 `OCR` 탭과 `YOLO Detection` 탭이 있습니다. `YOLO Detection` 탭의 기본 프롬프트는 Gemma4가 객체 목록을 JSON으로 반환하도록 요청합니다.

이미지를 선택한 뒤 상단 **YOLO Detection** 버튼을 누르면 `/api/detect`를 통해 Gemma4 모델에 이미지를 전송합니다. 응답에서 `detections` 또는 텍스트 안의 JSON을 파싱하여 인식 물체 이름, confidence 정확도, bounding box 좌표를 문자로 출력합니다.

결과창 아래에는 선택 이미지 위에 bounding box를 그린 박스 플롯이 표시됩니다. 박스 좌표는 `[x1, y1, x2, y2]` 형식을 사용하며, 0~1 정규화 좌표, 0~100 퍼센트 좌표, 픽셀 좌표를 최대한 자동으로 처리합니다.

선택된 이미지가 여러 개이면 한 번에 묶어서 전송하지 않고, 첫 번째 이미지 OCR 응답을 받은 뒤 다음 이미지를 전송하는 순서로 처리합니다. 결과 창에는 파일별 OCR 결과가 순서대로 누적 표시됩니다.

기본 요청 타임아웃은 600초입니다. 순차 처리 중 특정 이미지가 타임아웃되거나 실패하면 해당 파일 결과에 실패 메시지를 남기고 다음 파일 전송을 계속합니다.

---

## WebDAV 이미지

WebDAV 이미지는 브라우저가 직접 가져오지 않고 로컬 `client_service.py`가 대신 다운로드합니다. 따라서 CORS 제한을 피할 수 있고, Basic Auth가 필요한 WebDAV URL도 사용할 수 있습니다.

입력값:
- `WebDAV Path / Image URL`: WebDAV 디렉터리 경로 또는 실제 이미지 파일 URL
- `WebDAV User`: WebDAV 사용자 ID
- `WebDAV Password`: WebDAV 비밀번호 또는 앱 비밀번호

`주소 1`, `주소 2` 탭에 서로 다른 WebDAV 이미지 주소와 credential을 입력할 수 있습니다. `이미지 경로 확인`과 `WebDAV 경로 불러오기`는 현재 선택된 탭의 URL에서 이미지 파일을 검색하고, 찾은 원격 파일을 **이미지 파일을 놓거나 클릭해서 선택** 영역 아래의 **WebDAV 원격 파일** 목록에 표시합니다. 직접 이미지 URL이면 `HEAD` 요청을 우선 사용하고, 서버가 지원하지 않으면 `Range: bytes=0-0` GET 요청으로 최소 바이트만 확인합니다. 이미지가 아닌 WebDAV 디렉터리 응답이면 `PROPFIND Depth: 1`로 하위 이미지 파일을 검색합니다. 목록에서 파일을 체크한 뒤 **선택 파일 추가**를 누르면 업로드/클립보드 이미지와 동일하게 이미지 목록에 추가됩니다. 또는 원격 파일이 체크된 상태에서 **OCR 실행**을 누르면 선택된 WebDAV 파일을 자동으로 내려받아 OCR 프롬프트 전송에 포함합니다.

WebDAV 연결 설정은 `data/webdav_history.json`에 최대 20개까지 저장됩니다. `WebDAV 설정 저장`, `이미지 경로 확인`, `WebDAV 경로 불러오기`, `선택 파일 추가`를 실행하면 현재 WebDAV 탭의 URL/User/Password가 히스토리에 기록됩니다. 저장된 항목은 `저장된 WebDAV 설정`에서 다시 불러오거나 삭제할 수 있으며, 항목에는 저장 당시의 탭 번호도 함께 기록됩니다.

OCR 결과 이력(`data/ocr_history.json`)에는 사용한 이미지 이름과 함께 이미지별 `source`, `url`도 저장됩니다. WebDAV 원격 파일로 OCR을 실행한 경우 `webdav_urls`에 실제 접근 URL 목록이 함께 기록됩니다.

## OCR 결과 저장

OCR 결과 표시창은 각 결과 블록 상단에 `File:` 파일 이름을 표시하고, WebDAV 원격 파일이면 `WebDAV:` 접근 URL도 함께 표시합니다. 여러 이미지 OCR은 파일별 결과가 순서대로 누적됩니다.

좌측 **OCR 결과 저장** 패널에서 결과를 저장할 WebDAV 경로를 입력할 수 있습니다.
- `Result WebDAV Path`: OCR 결과 텍스트 파일을 업로드할 WebDAV 기본 디렉터리
- `Sub Path`: 기본 디렉터리 아래에 구분해서 저장할 하위 경로. 예: `site-a/2026-05`
- `Result WebDAV User`, `Result WebDAV Password`: 결과 저장 경로 접근 credential

**저장 경로 저장**을 누르면 결과 저장 경로 설정이 `data/result_webdav_history.json`에 최대 50개까지 보관됩니다. **WebDAV 저장**을 누르면 현재 OCR 결과 표시창의 전체 텍스트가 WebDAV로 업로드됩니다. 저장 파일 이름은 실행 장비의 hostname과 날짜/시간을 포함해 `hostname_YYYYMMDD_HHMMSS_mmm.txt` 형식으로 생성됩니다. `Sub Path`가 있으면 저장 전 WebDAV `MKCOL` 요청으로 하위 경로 생성을 시도한 뒤 해당 위치에 파일을 저장합니다.

## 연결 설정

좌측 패널에서 다음 값을 설정할 수 있습니다.
- `Gemma Model URL`: 모델 서버 기본 URL. 예: `http://keti-ev1.iptime.org:8082`
- `Generate Path`: OCR 요청 엔드포인트. 기본값: `/api/generate`
- `Status Path`: 연결 확인 엔드포인트. 기본값: `/api/status`
- `User ID`, `Password`: 서버 인증 정보
- `Model Override`: 서버 기본 모델 대신 사용할 모델명
- `Timeout`: 요청 제한 시간. 기본값은 600초입니다.
- `num_ctx`: 모델 컨텍스트 길이 옵션
- `Keep Alive`: Ollama 호환 keep-alive 옵션

## 모델 요청 형식

클라이언트는 `/api/generate`로 JSON을 전송합니다. 이미지 OCR을 위해 Ollama 호환 `images` 배열에 base64 이미지 데이터를 넣습니다.

```json
{
  "user_id": "admin",
  "password": "change-me-now",
  "prompt": "Extract all visible text from the image...",
  "images": ["base64-image-data"],
  "model": "optional-model",
  "keep_alive": "60m",
  "stream": false,
  "options": {
    "num_ctx": 8192
  }
}
```

YOLO Detection도 같은 `/api/generate` 경로와 이미지 배열을 사용하되, 프롬프트가 객체 탐지 JSON 출력을 요청합니다. 권장 응답 형식은 다음과 같습니다.

```json
{
  "detections": [
    {
      "label": "person",
      "confidence": 0.91,
      "bbox": [0.12, 0.18, 0.48, 0.92]
    }
  ]
}
```

응답은 다음 필드를 우선순위로 읽어 OCR 결과로 표시합니다.
- `response`
- `text`
- `output`
- `content`
- `message.content`
- `choices[0].message.content`
- `choices[0].text`

## 클립보드 이미지

브라우저 보안 정책상 클립보드 이미지 읽기는 보통 다음 조건에서 동작합니다.
- `http://127.0.0.1` 또는 HTTPS 환경
- 브라우저의 클립보드 접근 권한 허용
- 클립보드에 실제 이미지 데이터가 들어 있는 상태

버튼 방식이 실패하면 페이지 위에서 `Ctrl+V` 붙여넣기를 사용해 보세요.

## 데이터 파일

처음 실행하면 `data` 디렉터리가 자동 생성됩니다.
```text
data/client_config.json
data/ocr_history.json
data/webdav_history.json
data/result_webdav_history.json
```

`data/client_config.json`에는 Gemma 서버 및 WebDAV URL/인증 정보가 저장되므로 외부 공유에 주의하세요.

## 문제 해결

`python` 명령 실행 시 Microsoft Store 화면이 열리거나 `Python`만 출력되면 `py -3` 명령을 사용하세요.
```powershell
py -3 .\client_service.py
```

모델 연결이 실패하면 다음을 확인합니다.
- Gemma/Ollama 서버가 실행 중인지
- `Gemma Model URL` 포트가 맞는지
- `/api/status`, `/api/generate` 경로가 서버 구현과 일치하는지
- User ID와 Password가 서버 설정과 일치하는지
- 선택한 모델이 vision/image 입력을 지원하는지
- 서버가 최신 코드인지. 이미지 전송 확인 API는 서버의 `/api/test-image-transfer`가 필요합니다.
- WebDAV 이미지가 실패하면 URL이 직접 이미지 파일을 가리키는지, WebDAV 사용자/비밀번호가 맞는지, 응답 `Content-Type`이 `image/*`인지 확인합니다.

---

*자세한 API 구조 및 내부 함수 사양은 [spec.md](./spec.md)를 참고하세요.*

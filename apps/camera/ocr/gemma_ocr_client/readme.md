# Gemma OCR Client

클립보드 이미지 또는 업로드한 이미지 파일을 Gemma/Ollama 호환 파운데이션 모델에 전송하여 OCR을 수행하는 로컬 웹 클라이언트입니다.

참고 구현:

```text
E:\devel\BerePi\apps\deeplearning\LLM\5090\run_gemma4_ollama\client
```

## 구성

- `client_service.py`: 로컬 웹 서버, 설정 저장, 원격 모델 API 프록시
- `web/index.html`: OCR 클라이언트 화면
- `web/app.js`: 이미지 업로드, 클립보드 처리, OCR 요청, 결과 표시
- `web/styles.css`: UI 스타일
- `config/client_config.sample.json`: 기본 설정 샘플
- `data/client_config.json`: 실행 시 자동 생성되는 실제 설정 파일
- `data/ocr_history.json`: OCR 결과 히스토리

## 실행

```powershell
cd E:\devel\BerePi\apps\camera\ocr\gemma_ocr_client
py -3 .\client_service.py
```

또는 Python 실행 경로가 정상 등록되어 있으면:

```powershell
python .\client_service.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8775
```

포트는 환경 변수로 변경할 수 있습니다.

```powershell
$env:GEMMA_OCR_CLIENT_PORT="8780"
py -3 .\client_service.py
```

## 사용 방법

1. 좌측 `Gemma 연결` 패널에서 모델 서버 정보를 입력합니다.
2. `연결 확인`을 눌러 `/api/status` 응답을 확인합니다.
3. `설정 저장`을 눌러 현재 설정을 `data/client_config.json`에 저장합니다.
4. 이미지 파일을 드래그 앤 드롭하거나 클릭해서 선택합니다.
5. 클립보드 이미지는 `클립보드 이미지` 버튼 또는 `Ctrl+V`로 추가합니다.
6. WebDAV 이미지는 좌측 `WebDAV 이미지` 패널의 `주소 1` 또는 `주소 2` 탭에 이미지 URL, User, Password를 입력하고 `WebDAV 이미지 불러오기`를 누릅니다.
7. `이미지 전송 확인`으로 선택 이미지가 서버까지 도착하는지 확인합니다.
8. 필요한 경우 `OCR 프롬프트`를 수정합니다.
9. `OCR 실행`을 눌러 결과를 확인합니다.

`이미지 전송 확인`은 모델 추론을 실행하지 않고 서버의 `/api/test-image-transfer`로 이미지를 보내 수신 개수만 확인합니다. 선택된 이미지가 없으면 내장된 1x1 PNG 테스트 이미지를 보냅니다.

## WebDAV 이미지

WebDAV 이미지는 브라우저가 직접 가져오지 않고 로컬 `client_service.py`가 대신 다운로드합니다. 따라서 CORS 제한을 피할 수 있고, Basic Auth가 필요한 WebDAV URL도 사용할 수 있습니다.

입력값:

- `Image URL`: 실제 이미지 파일 URL
- `WebDAV User`: WebDAV 사용자 ID
- `WebDAV Password`: WebDAV 비밀번호 또는 앱 비밀번호

`주소 1`, `주소 2` 탭에 서로 다른 WebDAV 이미지 주소와 credential을 입력할 수 있습니다. `WebDAV 이미지 불러오기`는 현재 선택된 탭의 설정을 사용합니다. 불러온 이미지는 업로드/클립보드 이미지와 동일하게 이미지 목록에 추가되며, 체크된 이미지만 OCR 프롬프트 전송에 포함됩니다.

WebDAV 연결 설정은 `data/webdav_history.json`에 최대 100개까지 저장됩니다. `설정 저장` 또는 `WebDAV 이미지 불러오기`를 실행하면 현재 WebDAV 탭들의 URL/User/Password가 히스토리에 기록됩니다. 저장된 항목은 `저장된 WebDAV 설정`에서 다시 불러오거나 삭제할 수 있으며, 항목에는 저장 당시의 탭 번호도 함께 기록됩니다.

## 연결 설정

좌측 패널에서 다음 값을 설정할 수 있습니다.

- `Gemma Model URL`: 모델 서버 기본 URL. 예: `http://127.0.0.1:8082`
- `Generate Path`: OCR 요청 엔드포인트. 기본값: `/api/generate`
- `Status Path`: 연결 확인 엔드포인트. 기본값: `/api/status`
- `User ID`, `Password`: 서버 인증 정보
- `Model Override`: 서버 기본 모델 대신 사용할 모델명
- `Timeout`: 요청 제한 시간
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
- WebDAV 이미지가 실패하면 URL이 직접 이미지 파일을 가리키는지, WebDAV 사용자/비밀번호가 맞는지, 응답 `Content-Type`이 `image/*`인지 확인

## AI Agent pro processing for persona

### 원격 모델 사용

- 사이드바의 `AI 모델 제공자 선택`에서 `Remote Model`을 선택합니다.
- 기본 서버 주소는 `http://keties.iptime.org:4004`입니다.
- 서버에서 발급한 API Password와 원격 모델명을 입력합니다.
- 원격 서버는 `POST /api/generate` 형식을 사용하며, API Password는 인증 헤더로 전달됩니다.
- OpenAI 비교 탭에서도 `OpenAI와 비교할 모델 위치`를 `Remote Model`로 선택하면 동일한 원격 서버 응답과 비교할 수 있습니다.

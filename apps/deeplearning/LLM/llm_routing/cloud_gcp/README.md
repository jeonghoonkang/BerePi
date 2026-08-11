# Google AI Studio API Key 설정 및 실행 방법

`POST /api/gcp/generate`는 Google AI Studio에서 발급한 API Key를 사용해 Gemini API의 `generateContent`를 호출합니다. 기존 로컬 LLM 라우팅과 `/api/bedrock/generate`에는 영향을 주지 않습니다.

## 1. API Key 발급

1. [Google AI Studio](https://aistudio.google.com/app/apikey)에 로그인합니다.
2. API Key를 생성합니다.
3. 운영 시에는 키에 Gemini API 제한을 적용하고 외부에 노출하지 않습니다.

## 2. 설정 파일

수정할 파일은 `cloud_gcp/gcp_settings.json`입니다.

```json
{
  "api_key": "PUT_YOUR_GOOGLE_AI_STUDIO_API_KEY_HERE",
  "api_key_env": "GEMINI_API_KEY",
  "model_id": "gemma-4-31b-it",
  "api_version": "v1beta",
  "base_url": "https://generativelanguage.googleapis.com",
  "generation_config": {
    "maxOutputTokens": 1024,
    "temperature": 0.2,
    "topP": 0.9,
    "thinkingLevel": "minimal"
  }
}
```

- `api_key`: Google AI Studio에서 발급한 키. 실제 설정 파일은 Git에서 제외됩니다.
- `api_key_env`: 환경변수로 키를 전달할 때 사용할 변수 이름
- `model_id`: AI Studio/Gemini API에서 호출 가능한 모델 이름
- `api_version`: 기본값 `v1beta`
- `base_url`: Gemini API 주소
- `generation_config`: 기본 생성 옵션

보안을 위해 `api_key`를 빈 문자열로 두고 환경변수를 사용하는 방식을 권장합니다.

Linux:

```bash
export GEMINI_API_KEY="발급받은_GOOGLE_AI_STUDIO_API_KEY"
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="발급받은_GOOGLE_AI_STUDIO_API_KEY"
```

`api_key`와 환경변수가 모두 설정되어 있으면 설정 파일의 `api_key`를 우선 사용합니다.

다른 경로의 설정 파일을 사용하려면 다음 환경변수를 지정합니다.

```bash
export LLM_ROUTING_GCP_CONFIG=/secure/path/gcp_settings.json
```

## 3. 모델 변경

AI Studio에서 사용할 수 있는 모델 ID로 `model_id`를 변경합니다.

```json
"model_id": "gemma-4-31b-it"
```

설정 파일은 요청마다 다시 로드되므로 변경 후 서버 재시작 없이 다음 요청부터 적용됩니다. 단, 지정한 모델이 해당 API Key 및 Gemini API에서 실제 제공되어야 합니다.

Google AI Studio의 Gemini API에서 지원하는 Gemma 4 모델 ID는 `gemma-4-31b-it`와 `gemma-4-26b-a4b-it`입니다. `google/gemma-4-31b-it`처럼 `google/` 접두사가 붙은 자체 배포용 식별자는 이 API에서 사용하지 않습니다.

Gemma 4 thinking 기능은 `generation_config.thinkingLevel` 또는 요청의 `thinking_level`로 설정합니다. 허용 값은 `minimal`과 `high`입니다.

## 4. 서버 실행

Linux:

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/llm_routing
python3 -m pip install -r requirements.txt
./stop.sh
./start.sh
```

Windows PowerShell:

```powershell
cd E:\devel\BerePi\apps\deeplearning\LLM\llm_routing
py -3 -m pip install -r requirements.txt
py -3 server_routing.py --host 0.0.0.0 --port 4004
```

## 5. API 호출

```bash
curl -X POST http://keties.iptime.org:4004/api/gcp/generate \
  -H 'Content-Type: application/json' \
  -H 'X-LLM-Routing-Password: 라우팅_서버_비밀번호' \
  -d '{"prompt":"Google AI Studio API 연결 테스트입니다."}'
```

대화 메시지와 요청별 생성 옵션도 지원합니다.

```json
{
  "messages": [
    {"role": "system", "content": "한국어로 간결하게 답변하세요."},
    {"role": "user", "content": "클라우드 AI를 설명해주세요."}
  ],
  "temperature": 0.3,
  "max_tokens": 512,
  "top_p": 0.9,
  "top_k": 40,
  "thinking_level": "minimal"
}
```

`X-LLM-Routing-Password`는 Google API Key가 아니라 라우팅 서버의 `admin_password.conf`에 설정된 비밀번호입니다. 현재 엔드포인트는 비스트리밍 호출만 지원합니다.

## 6. 문제 해결

- API Key 누락: `gcp_settings.json`의 `api_key` 또는 `GEMINI_API_KEY`를 설정합니다.
- `400`: 요청 옵션 또는 모델 지원 형식을 확인합니다.
- `403`: API Key 제한, Gemini API 활성화 및 결제/지역 정책을 확인합니다.
- `404`: `model_id`가 Gemini API에서 제공되는 정확한 모델명인지 확인합니다.
- `429`: API 사용량 한도 또는 rate limit을 확인합니다.
- 라우팅 API `404`: 변경 코드를 배포한 뒤 라우팅 서버를 재시작합니다.

공식 문서:

- [Gemini API Key 사용](https://ai.google.dev/gemini-api/docs/api-key)
- [Gemini API generateContent](https://ai.google.dev/api/generate-content)
- [사용 가능한 Gemini 모델](https://ai.google.dev/gemini-api/docs/models)

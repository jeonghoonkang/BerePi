# GCP Vertex AI Gemma 연결 설정 및 실행 방법

이 모듈은 LLM Routing 서버의 독립 엔드포인트 `POST /api/gcp/generate`를 통해 GCP Vertex AI에 배포된 Gemma 모델을 호출합니다. 기존 로컬 모델 API와 AWS Bedrock API에는 영향을 주지 않습니다.

> `google/gemma-4-31b-it`는 이 프로젝트에서 사용하는 모델 식별자입니다. 실제 GCP Model Garden의 모델명 및 제공 여부와 다를 수 있으므로, 해당 모델을 Vertex AI에 배포한 뒤 생성된 Endpoint ID와 실제 서빙 모델명을 설정해야 합니다.

## 1. GCP 준비

1. GCP 프로젝트에서 Vertex AI API를 활성화합니다.
2. Model Garden 또는 사용자 모델을 Vertex AI Endpoint에 배포합니다.
3. 프로젝트 ID, 리전, 배포된 Endpoint ID를 확인합니다.
4. 서비스 계정에 최소 `aiplatform.endpoints.predict` 호출 권한을 포함하는 Vertex AI 권한을 부여합니다.
5. 서비스 계정 JSON을 서버의 안전한 디렉터리에 저장하거나 Compute Engine 서비스 계정을 사용합니다.

Endpoint ID 확인 예시:

```bash
gcloud ai endpoints list --project=YOUR_GCP_PROJECT_ID --region=us-central1
```

## 2. 패키지 설치

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/llm_routing
python3 -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd E:\devel\BerePi\apps\deeplearning\LLM\llm_routing
py -3 -m pip install -r requirements.txt
```

## 3. 설정 파일

`gcp_settings.json`을 수정합니다.

```json
{
  "project_id": "YOUR_GCP_PROJECT_ID",
  "location": "us-central1",
  "endpoint_id": "YOUR_VERTEX_ENDPOINT_ID",
  "model_id": "google/gemma-4-31b-it",
  "service_account_file_env": "GOOGLE_APPLICATION_CREDENTIALS",
  "access_token_env": "GOOGLE_OAUTH_ACCESS_TOKEN",
  "inference_config": {
    "max_tokens": 1024,
    "temperature": 0.2,
    "top_p": 0.9
  }
}
```

- `project_id`: GCP 프로젝트 ID
- `location`: Vertex AI Endpoint 리전
- `endpoint_id`: 배포가 완료된 Vertex AI Endpoint의 숫자 ID
- `model_id`: 배포 컨테이너가 인식하는 모델명
- `inference_config`: 기본 생성 옵션

다른 경로의 설정 파일은 `LLM_ROUTING_GCP_CONFIG` 환경변수로 지정할 수 있습니다.

```bash
export LLM_ROUTING_GCP_CONFIG=/secure/path/gcp_settings.json
```

## 4. 인증

서비스 계정 JSON 파일을 권장합니다. JSON 파일을 저장소 안에 복사하거나 Git에 커밋하지 마십시오.

Linux:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/secure/path/service-account.json
```

Windows PowerShell:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\secure\service-account.json"
```

개발 환경에서는 ADC를 설정할 수도 있습니다.

```bash
gcloud auth application-default login
```

짧은 수명의 OAuth 토큰을 직접 전달하는 방식도 지원합니다.

```bash
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
```

토큰은 만료되므로 운영 서버에서는 서비스 계정 또는 런타임 IAM 인증을 권장합니다.

## 5. 서버 실행

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/llm_routing
./stop.sh
./start.sh
```

Windows PowerShell:

```powershell
py -3 server_routing.py --host 0.0.0.0 --port 4004
```

## 6. GCP 전용 API 호출

```bash
curl -X POST http://keties.iptime.org:4004/api/gcp/generate \
  -H 'Content-Type: application/json' \
  -H 'X-LLM-Routing-Password: 라우팅_서버_비밀번호' \
  -d '{"prompt":"GCP Gemma 연결 테스트입니다."}'
```

메시지 형식도 지원합니다.

```json
{
  "messages": [
    {"role": "system", "content": "한국어로 답변하세요."},
    {"role": "user", "content": "간단히 자기소개를 해주세요."}
  ],
  "temperature": 0.2,
  "max_tokens": 512,
  "top_p": 0.9
}
```

현재 GCP 전용 엔드포인트는 비스트리밍 요청만 지원합니다. `X-LLM-Routing-Password`는 GCP 인증키가 아니라 라우팅 서버의 `admin_password.conf`에 설정된 비밀번호입니다.

## 7. API 구분

- `/api/generate`, `/generate`, `/api/chat`, `/v1/chat/completions`: 기존 Gemma/Ollama/OpenAI/vLLM 라우팅
- `/api/bedrock/generate`: AWS Bedrock
- `/api/gcp/generate`: GCP Vertex AI Gemma

## 8. 문제 해결

- `GCP project_id, location, and endpoint_id are required`: `gcp_settings.json`의 필수 값을 입력합니다.
- `google-auth is required`: `python3 -m pip install -r requirements.txt`를 실행합니다.
- ADC 또는 자격 증명 오류: `GOOGLE_APPLICATION_CREDENTIALS` 경로와 서비스 계정 JSON 권한을 확인합니다.
- `403 PermissionDenied`: 서비스 계정의 Vertex AI 호출 권한 및 프로젝트를 확인합니다.
- `404`: Endpoint ID, 리전, 배포 상태를 확인합니다.
- `Vertex AI returned HTTP 400`: 배포 컨테이너의 Chat Completions 호환 여부와 `model_id`를 확인합니다.
- 라우팅 API의 `404`: 변경된 서버 코드를 배포하고 프로세스를 재시작합니다.

관련 공식 문서:

- [Vertex AI에서 Gemma 사용](https://cloud.google.com/vertex-ai/generative-ai/docs/open-models/use-gemma)
- [Vertex AI에서 OpenAI 라이브러리 사용](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/call-vertex-using-openai-library)
- [Application Default Credentials 설정](https://cloud.google.com/docs/authentication/provide-credentials-adc)

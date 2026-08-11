# AWS Bedrock 연결 설정 및 실행 방법

이 디렉터리는 LLM Routing 서버의 AWS Bedrock 전용 호출 기능을 제공합니다.

- 기존 `/api/generate`, `/generate`, `/api/chat`, `/v1/chat/completions`는 기존 로컬·원격 LLM 대상에 전달됩니다.
- `/api/bedrock/generate` 요청만 AWS Bedrock으로 전달됩니다.
- `llm_targets.json`은 Bedrock 호출을 위해 수정할 필요가 없습니다.

## 1. 사전 준비

AWS 계정에서 다음 사항을 준비합니다.

1. 사용할 AWS 리전에서 Amazon Bedrock 모델 사용 권한을 활성화합니다.
2. 호출할 모델 또는 Inference Profile ID를 확인합니다.
3. 실행 주체에 `bedrock:InvokeModel` 권한을 부여합니다.
4. AWS Access Key 또는 Bedrock API Key를 준비합니다.

Python 의존성을 설치합니다.

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/llm_routing
python3 -m pip install -r requirements.txt
```

Windows PowerShell에서는 다음과 같이 실행할 수 있습니다.

```powershell
cd E:\devel\BerePi\apps\deeplearning\LLM\llm_routing
py -3 -m pip install -r requirements.txt
```

## 2. Bedrock 설정 파일

실제 설정 파일은 `bedrock_settings.json`입니다. 파일이 없다면 예제 파일을 복사합니다.

Linux:

```bash
cp cloud_bedrock/bedrock_settings.example.json cloud_bedrock/bedrock_settings.json
```

Windows PowerShell:

```powershell
Copy-Item cloud_bedrock\bedrock_settings.example.json cloud_bedrock\bedrock_settings.json
```

설정 예시:

```json
{
  "region": "us-east-1",
  "model_id": "amazon.nova-micro-v1:0",
  "access_key_id_env": "AWS_ACCESS_KEY_ID",
  "secret_access_key_env": "AWS_SECRET_ACCESS_KEY",
  "session_token_env": "AWS_SESSION_TOKEN",
  "bearer_token_env": "AWS_BEARER_TOKEN_BEDROCK",
  "inference_config": {
    "maxTokens": 1024,
    "temperature": 0.2,
    "topP": 0.9
  }
}
```

설정 항목:

- `region`: Bedrock을 호출할 AWS 리전
- `model_id`: Foundation Model ID 또는 Inference Profile ID
- `access_key_id_env`: Access Key ID를 읽을 환경변수 이름
- `secret_access_key_env`: Secret Access Key를 읽을 환경변수 이름
- `session_token_env`: 임시 자격 증명의 Session Token 환경변수 이름
- `bearer_token_env`: Bedrock API Key 환경변수 이름
- `inference_config.maxTokens`: 최대 출력 토큰 수
- `inference_config.temperature`: 응답 무작위성
- `inference_config.topP`: nucleus sampling 값

다른 위치의 설정 파일을 사용하려면 서버 실행 전에 경로를 지정합니다.

```bash
export LLM_ROUTING_BEDROCK_CONFIG=/secure/path/bedrock_settings.json
```

```powershell
$env:LLM_ROUTING_BEDROCK_CONFIG="C:\secure\bedrock_settings.json"
```

## 3. AWS 인증 설정

실제 비밀키는 `bedrock_settings.json`, `credentials.example.env` 또는 소스 코드에 입력하지 않습니다. 서버 프로세스의 환경변수로 전달합니다.

### 방법 A: AWS Access Key

Linux:

```bash
export AWS_ACCESS_KEY_ID="발급받은_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="발급받은_SECRET_ACCESS_KEY"

# STS 임시 자격 증명인 경우에만 설정
export AWS_SESSION_TOKEN="발급받은_SESSION_TOKEN"
```

Windows PowerShell:

```powershell
$env:AWS_ACCESS_KEY_ID="발급받은_ACCESS_KEY_ID"
$env:AWS_SECRET_ACCESS_KEY="발급받은_SECRET_ACCESS_KEY"

# STS 임시 자격 증명인 경우에만 설정
$env:AWS_SESSION_TOKEN="발급받은_SESSION_TOKEN"
```

EC2 IAM Role, ECS Task Role 또는 AWS CLI 프로필을 사용하는 경우에는 boto3의 기본 자격 증명 체인이 자동으로 사용됩니다.

### 방법 B: Bedrock API Key

Linux:

```bash
export AWS_BEARER_TOKEN_BEDROCK="발급받은_BEDROCK_API_KEY"
```

Windows PowerShell:

```powershell
$env:AWS_BEARER_TOKEN_BEDROCK="발급받은_BEDROCK_API_KEY"
```

`credentials.example.env`는 필요한 환경변수 이름을 보여 주는 참고 파일이며 서버가 자동으로 읽는 파일은 아닙니다.

## 4. 라우팅 서버 실행

환경변수는 서버를 실행하는 동일한 터미널 또는 서비스 환경에 설정되어 있어야 합니다.

Linux 포그라운드 실행:

```bash
cd /path/to/BerePi/apps/deeplearning/LLM/llm_routing
./run.sh
```

Linux 백그라운드 실행:

```bash
./start.sh
```

재시작:

```bash
./stop.sh
./start.sh
```

Windows PowerShell 포그라운드 실행:

```powershell
cd E:\devel\BerePi\apps\deeplearning\LLM\llm_routing
py -3 server_routing.py --host 0.0.0.0 --port 4004
```

기본 포트는 `4004`입니다. 설정이나 인증 환경변수를 변경했다면 반드시 서버를 재시작해야 합니다.

## 5. Bedrock API 호출

단일 프롬프트 호출:

```bash
curl -X POST http://keties.iptime.org:4004/api/bedrock/generate \
  -H 'Content-Type: application/json' \
  -H 'X-LLM-Routing-Password: 라우팅_서버_비밀번호' \
  -d '{"prompt":"AWS Bedrock 연결 테스트입니다. 간단히 응답하세요."}'
```

대화 메시지 호출:

```bash
curl -X POST http://keties.iptime.org:4004/api/bedrock/generate \
  -H 'Content-Type: application/json' \
  -H 'X-LLM-Routing-Password: 라우팅_서버_비밀번호' \
  -d '{
    "messages": [
      {"role":"system", "content":"한국어로 간결하게 답변하세요."},
      {"role":"user", "content":"Amazon Bedrock이 무엇인가요?"}
    ],
    "temperature": 0.2,
    "max_tokens": 512,
    "top_p": 0.9
  }'
```

인증된 웹 관리 세션을 사용하지 않는 API 호출에는 `X-LLM-Routing-Password`가 필요합니다. 이 값은 상위 디렉터리의 `admin_password.conf` 또는 `LLM_ROUTING_ADMIN_PASSWORD` 환경변수에 설정된 라우팅 서버 비밀번호입니다. AWS 키와는 다른 값입니다.

현재 `/api/bedrock/generate`는 비스트리밍 요청만 지원하므로 `"stream": true`를 보내면 오류가 반환됩니다.

## 6. 응답 예시

```json
{
  "ok": true,
  "target_name": "AWS Bedrock",
  "api_type": "bedrock",
  "model": "amazon.nova-micro-v1:0",
  "response": "Bedrock 모델의 응답 내용",
  "response_seconds": 1.23
}
```

## 7. 문제 해결

- `boto3 is required`: `python3 -m pip install -r requirements.txt`를 실행합니다.
- `Bedrock config file not found`: `cloud_bedrock/bedrock_settings.json` 파일 존재 여부를 확인합니다.
- `region and model_id are required`: 설정 파일의 `region`, `model_id` 값을 확인합니다.
- `Unable to locate credentials`: AWS 인증 환경변수 또는 실행 환경의 IAM Role을 확인합니다.
- `AccessDeniedException`: IAM의 `bedrock:InvokeModel` 권한과 해당 모델 사용 권한을 확인합니다.
- `ValidationException`: 모델 ID와 리전의 조합, 해당 모델의 Converse API 지원 여부를 확인합니다.
- `invalid api password`: AWS 키가 아니라 LLM Routing 서버 비밀번호와 `X-LLM-Routing-Password` 헤더를 확인합니다.
- 신규 엔드포인트가 `404`를 반환: 변경된 코드를 서버에 배포하고 라우팅 서버를 재시작했는지 확인합니다.

AWS 공식 문서:

- [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-call.html)
- [Boto3 Bedrock Runtime Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html)
- [Amazon Bedrock API Key 사용](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html)

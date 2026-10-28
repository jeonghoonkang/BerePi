# DGX Spark vLLM OCR 및 사진 설명 입력 처리

일반 `/v1/chat/completions` 대화에도 한국어 기본 응답 지시를 자동 추가합니다.
기존 시스템 지시와 대화 이력, 생성 옵션은 유지하고 지시 중복 삽입은 방지합니다.
사용자 또는 기존 시스템 지시가 다른 언어를 명시하면 그 언어를 따르며,
원문·코드·고유명사를 임의 번역하지 않습니다. OCR은 원문 언어 전사를 유지합니다.

이미지와 함께 최신 사용자 메시지에 `ocr please`를 넣으면 OCR 원문 전사,
`explain please` 또는 `please explain`을 넣으면 한국어 사진 설명 시스템 프롬프트를 적용합니다.
두 요청이 함께 있으면 OCR을 우선합니다. 두 기능 모두 기존 시스템 메시지는 유지하고
이전 사용자·어시스턴트·도구 메시지는 제외하여 과거 이미지와 혼동하지 않도록 합니다.
`explain please`는 OCR 확인 과정 없이 사진의 대상·특징·배치를 설명합니다.
사진에 없는 사실을 추측하지 않도록 지시하며 이미지가 없는 텍스트 요청에는 적용하지 않습니다.
단일 노드와 멀티노드 모두 기존 미들웨어 등록을 그대로 사용합니다.
vLLM API의 SSE/JSON 응답에 별도 `thinking...` 텍스트를 삽입하지 않습니다.

`run.sh`와 `multinode/run_node1_head.sh`는 `sequential_prompt.OCRPromptMiddleware`를
vLLM의 `--middleware` 옵션에 등록합니다. 파일 하나를 컨테이너에 읽기 전용으로 마운트하므로
추가 Python 패키지 없이 동작합니다.
[vLLM 공식 미들웨어 옵션](https://docs.vllm.ai/en/v0.28.0/cli/serve/#--middleware)을 사용합니다.

## 실행과 적용

### Hugging Face 토큰 파일 추가

현재 실행 스크립트가 기본으로 읽는 파일명은 **`hf_key.txt`**입니다.
`hfkey.txt`가 아니라 밑줄이 있는 이름으로, `run.sh`와 같은 `server` 디렉터리에 생성하세요.
Hugging Face 계정에서 사용할 모델을 읽을 수 있는 토큰을 준비합니다.
접근 승인이 필요한 모델은 해당 계정으로 모델 사용 조건 동의·승인을 먼저 완료해야 합니다.

아래 예시는 DGX 서버의 Bash에서 실행합니다. 저장소 위치가 다르면 첫 경로를 바꾸세요.
토큰은 화면이나 명령어 기록에 직접 남기지 않도록 숨김 입력으로 받습니다.

```bash
cd ~/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server
(
  umask 077
  read -r -s -p 'Hugging Face token: ' hf_token
  printf '\n'
  printf '%s\n' "$hf_token" > hf_key.txt
  chmod 600 hf_key.txt
)
```

파일 내용은 `hf_...` 형태의 **토큰 한 줄만** 있어야 합니다.
`HF_TOKEN=`, 따옴표, 설명은 넣지 않습니다. 다음 명령으로 파일 내용 노출 없이 확인합니다.

```bash
test -s hf_key.txt && echo '토큰 파일이 존재하며 비어 있지 않습니다.'
```

토큰 파일은 Git에 커밋하지 마세요. 아래 명령으로 현재 로컬 저장소의 제외 목록에 추가할 수 있습니다.

```bash
printf '\n/apps/deeplearning/LLM/dgx_spark/server/hf_key.txt\n' >> "$(git rev-parse --git-path info/exclude)"
git check-ignore hf_key.txt
```

`bash run.sh 26000`을 실행하면 파일을 읽어 컨테이너의 `HF_TOKEN` 환경 변수로 전달합니다.
멀티노드도 기본적으로 같은 `server/hf_key.txt`를 사용하며, 각 노드의 로컬 저장소에 준비해야 합니다.
멀티노드 스크립트에서만 다른 파일명·경로를 `KEY_FILE`로 지정할 수 있습니다.
예를 들어 이미 `server/hfkey.txt`로 만든 경우 Head 실행은 다음과 같습니다.

```bash
KEY_FILE="$PWD/hfkey.txt" bash multinode/run_node1_head.sh
```

이 경우 `hfkey.txt`도 Git 제외 목록에 추가하세요. 단일 노드 `run.sh`는 `KEY_FILE`을
외부에서 지정해도 기본 경로로 덮어쓰므로 `hf_key.txt`라는 이름을 사용해야 합니다.

기존 vLLM 프로세스에는 코드를 자동으로 주입할 수 없습니다. 실행 중인 서버를 종료한 뒤
수정된 스크립트로 한 번 재시작하세요. 기존 API 포트를 그대로 사용합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/dgx_spark/server
bash run.sh 26000
```

DGX 머신에서는 위 경로를 실제 저장소 경로로 바꿉니다. 멀티노드 구성은 기존처럼
`multinode/run_node1_head.sh`와 Worker 실행 스크립트를 사용합니다. 입력 처리는 Head에서 수행합니다.

## 입력과 처리

`POST /v1/chat/completions`의 **마지막 user 메시지**에 파일과 함께
`OCR 해주세요`, `첨부 문서 OCR 실행해 주세요`, `Please perform OCR on this file` 같은
명시적인 요청이 있으면 확인 질문 없이 OCR 시스템 프롬프트를 추가합니다.
기존 시스템 메시지가 있으면 그 내용을 유지하고 뒤에 OCR 지시를 추가합니다.
원문 언어·읽기 순서·문단·표·페이지 구분을 보존하고, 불명확한 글자는 `[illegible]`로 표시하도록 지시합니다.

OCR 요청이 없거나 `OCR 하지 마세요` 같은 부정 요청이면 시스템 프롬프트를 추가하지 않습니다.
첨부 파일명·첨부 내용·이전 대화의 OCR 문구만으로는 OCR 모드를 켜지 않습니다.
이 미들웨어는 확인 질문이나 답변 대기 상태를 만들지 않습니다.

JSON 요청의 최상위 `files`에 파일명과 Base64를 넣을 수 있습니다. 예를 들어 Python 클라이언트에서는:

```python
import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen

path = Path("scan.png")  # 확장자보다 실제 파일 시그니처를 우선합니다.
payload = {
    "model": "google/gemma-4-31b-it",
    "messages": [{"role": "user", "content": "첨부 파일 OCR 해주세요"}],
    "files": [{
        "name": path.name,
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }],
    "max_tokens": 2048,
}
request = Request("http://DGX_HOST:26000/v1/chat/completions",
                  data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
with urlopen(request, timeout=600) as response:
    print(json.load(response)["choices"][0]["message"]["content"])
```

OpenAI 호환 클라이언트에서 `messages[].content`의 `image_url`을 사용하는 경우에도
같은 user 메시지의 텍스트에서 OCR 요청을 감지합니다. `type: "file"`과
`file: {filename, file_data}`도 지원하며 `file_data`에는 Base64 또는 Base64 data URL을 넣습니다.
HTTP multipart 업로드, `file_id`, 로컬 파일 경로만 보내는 입력은 지원하지 않습니다.
클라이언트는 파일 데이터를 API 요청에 포함해야 합니다.

- 이미지: 실제 파일 종류를 판별하여 Base64 `image_url` 입력으로 변환합니다.
- PDF: Poppler의 `pdftoppm`으로 각 페이지를 PNG로 변환합니다. **vLLM 컨테이너 안에** Poppler가 있어야 합니다.
- UTF-8 텍스트: 디코딩한 파일 내용을 user 메시지에 포함합니다.
- 일반 바이너리: 이미지처럼 위장하지 않고 파일명과 Base64 데이터를 텍스트 입력에 포함합니다.
  OCR 시스템 프롬프트는 추가되지만, 임의 바이너리 형식의 문자를 추출할 수 있다는 보장은 없습니다.

최대 첨부 10개, 파일 합계 20 MiB, 일반 바이너리당 256 KiB, PDF당 20페이지를 지원합니다.
PDF는 긴 변이 최대 1600px인 이미지로 변환합니다. 여러 페이지 입력에는 모델의 이미지 개수 및
컨텍스트 한도도 적용됩니다. `stream`, `temperature`, `max_tokens` 등 생성 옵션과 SSE 응답은 유지합니다.
`/v1/completions`, `/health`, `/v1/models` 등 다른 경로에는 이 처리를 적용하지 않습니다.

## PDF를 사용하는 경우

기본 이미지에 `pdftoppm`이 없다면 다음과 같이 Poppler를 포함한 이미지를 빌드할 수 있습니다.

```bash
docker build -f Dockerfile.ocr -t berepi-vllm-ocr .
IMAGE=berepi-vllm-ocr bash run.sh 26000
```

멀티노드는 기반 이미지를 맞추어 빌드하고 양쪽 노드에 동일한 이미지를 준비합니다.

```bash
docker build -f Dockerfile.ocr --build-arg BASE_IMAGE=vllm/vllm-openai:gemma4-cu130 -t berepi-vllm-ocr .
```

이후 Head와 Worker 모두 `IMAGE=berepi-vllm-ocr`로 실행합니다.

## 검증

```bash
python3 -m unittest discover -s . -p 'test_*.py'
bash -n run.sh multinode/run_node1_head.sh
```

테스트는 vLLM에 전달될 요청, 시스템 메시지 보존, 바이너리/이미지/PDF 분기,
부정 요청, 잘못된 입력, HTTP 본문 재작성과 스트리밍 응답 통과를 검증합니다.
실제 DGX GPU 추론 및 OCR 정확도는 서버에서 별도 확인해야 합니다.

# Gemma4 LiteLLM Gateway

This directory runs two Gemma4 vLLM backends behind one LiteLLM OpenAI-compatible
proxy:

- `google/gemma-4-31b-it`
- `nvidia/gemma-4-31b-it-nvfp4`

Remote access is controlled by LiteLLM authentication. Clients must send:

```text
Authorization: Bearer <LITELLM_MASTER_KEY>
```

An optional IP allowlist can be set with `LITELLM_ALLOWED_IPS`.

## Install

```bash
cd apps/deeplearning/litellm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
```

Edit `.env` and replace `LITELLM_MASTER_KEY`.

## Start Backends

Start the Google BF16 model on port `8001`:

```bash
./scripts/run_vllm_google_gemma4_31b_it.sh
```

Start the NVIDIA NVFP4 model on port `8002`:

```bash
./scripts/run_vllm_nvidia_gemma4_31b_it_nvfp4.sh
```

The BF16 Google model is large and typically needs an 80 GB-class GPU or tensor
parallelism. The NVIDIA NVFP4 checkpoint is intended for vLLM and uses less
memory, but current vLLM/CUDA support may still depend on your GPU, driver, and
vLLM version.

## Start LiteLLM

Local-only:

```bash
./scripts/run_litellm.sh
```

Remote:

```bash
./scripts/run_litellm.sh --remote
```

With a custom port:

```bash
./scripts/run_litellm.sh --remote --port 4001
```

## Gateway-Only Check

You can verify the LiteLLM gateway without starting either vLLM backend. This
checks that the proxy is reachable, the master key is accepted, and the configured
model list is visible.

```bash
./scripts/run_litellm.sh
```

In another terminal:

```bash
curl http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

Or use the helper script:

```bash
python scripts/gateway_check.py
```

This does not run inference and does not require `8001` or `8002` vLLM backends
to be running.

## Test

```bash
curl http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nvidia/gemma-4-31b-it-nvfp4",
    "messages": [{"role": "user", "content": "Reply in one short Korean sentence."}],
    "max_tokens": 64
  }'
```

Or use:

```bash
python scripts/smoke_test.py --model nvidia/gemma-4-31b-it-nvfp4
```

## Access Control

- Keep vLLM backends bound to `127.0.0.1`.
- Use `--remote` only on the LiteLLM proxy.
- Use a strong `LITELLM_MASTER_KEY` beginning with `sk-`.
- Set `LITELLM_ALLOWED_IPS` when only known clients should connect.
- Put HTTPS or a VPN in front of the proxy for production remote access.

LiteLLM virtual per-user keys require a database. The included setup uses the
single master key path because it is simple and works without extra services.

---

# Gemma4 LiteLLM Gateway 한국어 안내

이 디렉터리는 Gemma4 vLLM 백엔드 2개를 LiteLLM OpenAI 호환 프록시 뒤에서
운영하기 위한 예제입니다.

- `google/gemma-4-31b-it`
- `nvidia/gemma-4-31b-it-nvfp4`

원격 접속은 LiteLLM 인증으로 통제합니다. 클라이언트는 모든 요청에 아래
헤더를 포함해야 합니다.

```text
Authorization: Bearer <LITELLM_MASTER_KEY>
```

필요하면 `.env`의 `LITELLM_ALLOWED_IPS`로 접속 가능한 IP를 제한할 수
있습니다.

## 설치

```bash
cd apps/deeplearning/litellm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
```

`.env` 파일을 열어 `LITELLM_MASTER_KEY`를 반드시 강한 값으로 바꾸세요.
키는 `sk-`로 시작해야 합니다.

## 백엔드 시작

Google BF16 모델을 `8001` 포트에서 시작합니다.

```bash
./scripts/run_vllm_google_gemma4_31b_it.sh
```

NVIDIA NVFP4 모델을 `8002` 포트에서 시작합니다.

```bash
./scripts/run_vllm_nvidia_gemma4_31b_it_nvfp4.sh
```

Google BF16 모델은 크기 때문에 보통 80 GB급 GPU 또는 tensor parallelism이
필요합니다. NVIDIA NVFP4 체크포인트는 vLLM 추론용이며 메모리 사용량이 더
작지만, 실제 실행 가능 여부는 GPU, 드라이버, CUDA, vLLM 버전에 영향을
받습니다.

## LiteLLM 시작

로컬 접속만 허용하려면:

```bash
./scripts/run_litellm.sh
```

원격 접속을 허용하려면:

```bash
./scripts/run_litellm.sh --remote
```

포트를 바꾸려면:

```bash
./scripts/run_litellm.sh --remote --port 4001
```

## 게이트웨이 연결만 검증

vLLM 백엔드를 실행하지 않고 LiteLLM 게이트웨이만 확인할 수 있습니다. 이
검사는 프록시 접속 가능 여부, master key 인증, 설정된 모델 목록 노출 여부만
확인합니다.

먼저 LiteLLM만 실행합니다.

```bash
./scripts/run_litellm.sh
```

다른 터미널에서 `/v1/models`를 호출합니다.

```bash
curl http://127.0.0.1:4000/v1/models \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}"
```

또는 helper 스크립트를 사용할 수 있습니다.

```bash
python scripts/gateway_check.py
```

이 검증은 추론을 수행하지 않으며, `8001` 또는 `8002` vLLM 백엔드가 실행 중일
필요가 없습니다.

## 테스트

```bash
curl http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nvidia/gemma-4-31b-it-nvfp4",
    "messages": [{"role": "user", "content": "한 문장으로 짧게 한국어로 응답해 주세요."}],
    "max_tokens": 64
  }'
```

또는 Python 테스트 스크립트를 사용할 수 있습니다.

```bash
python scripts/smoke_test.py --model nvidia/gemma-4-31b-it-nvfp4
```

## 접근 권한 통제

- vLLM 백엔드는 기본값인 `127.0.0.1` 바인딩을 유지하세요.
- 외부 접속은 LiteLLM 프록시에만 `--remote`로 여세요.
- `LITELLM_MASTER_KEY`는 `sk-`로 시작하는 강한 키로 설정하세요.
- 특정 클라이언트만 허용하려면 `LITELLM_ALLOWED_IPS`를 설정하세요.
- 운영 환경에서는 HTTPS 프록시나 VPN 뒤에 두는 것을 권장합니다.

LiteLLM의 사용자별 virtual key 기능은 데이터베이스가 필요합니다. 이 구성은
추가 서비스 없이 바로 쓰기 쉽도록 단일 master key 방식을 사용합니다.

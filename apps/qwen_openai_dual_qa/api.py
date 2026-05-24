import os
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


QWEN_MODEL = os.environ.get("QWEN_MODEL", "Qwen/Qwen1.5-7B-Chat")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

Provider = Literal["openai", "qwen"]

app = FastAPI(title="Dual Q&A API", version="1.0.0")


class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="모델에 전달할 프롬프트")
    provider: Provider = Field("openai", description="응답을 생성할 모델 제공자")
    max_length: int = Field(512, ge=1, le=4096, description="Qwen 생성 최대 길이")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="OpenAI/Qwen temperature")


class AskResponse(BaseModel):
    provider: Provider
    model: str
    prompt: str
    answer: str


def get_openai_api_key() -> str | None:
    """Load OpenAI key from env or local nocommit_key.txt files."""
    if OPENAI_API_KEY:
        return OPENAI_API_KEY

    key_candidates = [
        os.path.join(os.path.dirname(__file__), "nocommit_key.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "nocommit_key.txt"),
    ]
    for candidate in key_candidates:
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read().strip()
    return None


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    api_key = get_openai_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY 환경 변수를 설정하세요.")
    return OpenAI(api_key=api_key)


@lru_cache(maxsize=1)
def get_qwen_generator():
    import torch

    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL)
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        model = AutoModelForCausalLM.from_pretrained(QWEN_MODEL, device_map=device)
        return pipeline("text-generation", model=model, tokenizer=tokenizer, device=device)

    model = AutoModelForCausalLM.from_pretrained(QWEN_MODEL, device_map="auto")
    return pipeline("text-generation", model=model, tokenizer=tokenizer)


def answer_openai(prompt: str, temperature: float) -> str:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def answer_qwen(prompt: str, max_length: int, temperature: float) -> str:
    generator = get_qwen_generator()
    generation_args = {
        "max_length": max_length,
        "do_sample": temperature > 0,
    }
    if temperature > 0:
        generation_args["temperature"] = temperature

    response = generator(prompt, **generation_args)
    generated_text = response[0]["generated_text"]
    return generated_text[len(prompt) :].strip()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt는 비어 있을 수 없습니다.")

    try:
        if request.provider == "qwen":
            answer = answer_qwen(prompt, request.max_length, request.temperature)
            model = QWEN_MODEL
        else:
            answer = answer_openai(prompt, request.temperature)
            model = OPENAI_MODEL
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return AskResponse(
        provider=request.provider,
        model=model,
        prompt=prompt,
        answer=answer,
    )

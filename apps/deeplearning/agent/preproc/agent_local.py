import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _normalize_server_url(server_url: str) -> str:
    return (server_url or DEFAULT_OLLAMA_URL).strip().rstrip("/")


def _build_auth_headers(api_password: str = None) -> dict:
    password = (api_password or "").strip()
    if not password:
        return {}
    return {
        "X-LLM-Routing-Password": password,
        "X-API-Key": password,
        "Authorization": f"Bearer {password}",
    }

def generate_enhanced_prompt_local(
    user_input: str,
    model_name: str,
    config_data: dict,
    include_thinking: bool = False,
    server_url: str = DEFAULT_OLLAMA_URL,
    api_password: str = None,
):
    persona = config_data.get("persona", "")
    guidelines = "\n- ".join(config_data.get("guidelines", []))
    output_format = config_data.get("output_format", "")
    
    system_instruction = f"역할(Persona):\n{persona}\n\n지침 및 규칙(Guidelines & Rules):\n- {guidelines}\n\n출력 방식(Output Format):\n{output_format}"
    
    examples = config_data.get("examples", [])
    if examples:
        system_instruction += "\n\n[참고용 입출력 예시]\n"
        for i, ex in enumerate(examples, 1):
            system_instruction += f"예시 {i}. 입력: {ex.get('user_input', '')}\n예시 {i}. 출력:\n{ex.get('assistant_output', '')}\n\n"
            
    # Ollama API doesn't fully support system prompts in standard generate API in all models consistently,
    # so we combine it into the main prompt to be safe.
    full_prompt = f"System Instruction:\n{system_instruction}\n\nUser Request:\n{user_input}"
    
    try:
        payload = {"model": model_name, "prompt": full_prompt, "stream": False}
        if include_thinking:
            payload["think"] = True

        response = requests.post(
            f"{_normalize_server_url(server_url)}/api/generate",
            headers=_build_auth_headers(api_password),
            json=payload,
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            # Ollama generate, OpenAI-compatible, and LLMRouting wrapper responses.
            generated_text = data.get("response") or data.get("output_text") or data.get("text")
            if not generated_text and data.get("choices"):
                choice = data["choices"][0]
                generated_text = choice.get("text") or choice.get("message", {}).get("content", "")
            if not generated_text and isinstance(data.get("data"), dict):
                nested = data["data"]
                generated_text = nested.get("response") or nested.get("output_text") or nested.get("text")
            if include_thinking:
                return {
                    "response": generated_text or "",
                    "thinking": data.get("thinking", "")
                }
            return generated_text or ""
        else:
            return f"모델 API 에러 ({response.status_code}): {response.text}"
    except requests.exceptions.ConnectionError:
        return f"모델 서버 통신 오류: {_normalize_server_url(server_url)} 접속 상태를 확인해주세요."
    except requests.exceptions.Timeout:
        return f"모델 서버 응답 시간 초과: {_normalize_server_url(server_url)}"
    except Exception as e:
        return f"오류 발생: {str(e)}"

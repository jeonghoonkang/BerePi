import requests

def generate_enhanced_prompt_local(user_input: str, model_name: str, config_data: dict) -> str:
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
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": full_prompt, "stream": False},
            timeout=120
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            return f"Ollama API 에러 ({response.status_code}): {response.text}"
    except requests.exceptions.ConnectionError:
        return "로컬 모델 통신 오류: Ollama 데몬이 실행 중인지 확인해주세요 (http://localhost:11434 접속 불가)."
    except Exception as e:
        return f"오류 발생: {str(e)}"

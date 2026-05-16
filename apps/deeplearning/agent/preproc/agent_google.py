import json
import os
from google import genai
from google.genai import types
from pathlib import Path

def load_config(config_path="persona/persona_config.json"):
    """
    개발자가 설정한 페르소나, 지침, 출력 방식이 담긴 설정 파일을 읽어옵니다.
    """
    base_dir = Path(__file__).parent
    full_path = base_dir / config_path
    
    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_system_instruction(config):
    """
    설정 파일의 내용을 바탕으로 Gemini 모델에 주입할 시스템 지시어(System Prompt)를 생성합니다.
    """
    persona = config.get("persona", "")
    guidelines = "\n- ".join(config.get("guidelines", []))
    output_format = config.get("output_format", "")
    
    system_instruction = f"""
역할(Persona):
{persona}

지침 및 규칙(Guidelines & Rules):
- {guidelines}

출력 방식(Output Format):
{output_format}
"""
    
    # 샘플 예제(Few-shot)가 설정 파일에 있다면 추가합니다.
    examples = config.get("examples", [])
    if examples:
        system_instruction += "\n\n[참고용 입출력 예시]\n"
        for i, ex in enumerate(examples, 1):
            system_instruction += f"예시 {i}. 입력: {ex.get('user_input', '')}\n예시 {i}. 출력:\n{ex.get('assistant_output', '')}\n\n"
            
    return system_instruction.strip()

def generate_enhanced_prompt(user_input: str, config_path: str = "persona/persona_config.json", api_key: str = None, config_data: dict = None) -> str:
    """
    사용자의 입력을 받아 Google Generative AI (Gemini)를 통해 보강된 프롬프트를 생성합니다.
    """
    # 환경변수에서 API 키 로드 (export GEMINI_API_KEY="your-api-key")
    resolved_api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if resolved_api_key:
        resolved_api_key = resolved_api_key.strip()
        
    if not resolved_api_key:
        return "오류: GEMINI_API_KEY 환경변수가 설정되지 않았습니다. 터미널에서 API 키를 설정하거나 UI에서 입력해주세요."
    
    # 설정 데이터가 전달되지 않은 경우 파일에서 로드
    if config_data is None:
        try:
            config = load_config(config_path)
        except FileNotFoundError:
            return f"오류: 설정 파일({config_path})을 찾을 수 없습니다."
    else:
        config = config_data
        
    system_instruction = build_system_instruction(config)
    
    try:
        # 새로운 google.genai 클라이언트 초기화 및 호출
        client = genai.Client(api_key=resolved_api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
            )
        )
        return response.text
    except Exception as e:
        return f"문장 생성 중 오류가 발생했습니다: {str(e)}"

if __name__ == "__main__":
    print("=== AI 프롬프트 보강 에이전트 (Google SDK) ===")
    print("1. 직접 프롬프트 입력하여 테스트")
    print("2. 샘플 예제(설정 파일)를 이용한 자동 테스트")
    
    choice = input("\n메뉴를 선택하세요 (1 또는 2, 기본값 1): ").strip()
    
    if choice == '2':
        config_data = load_config()
        examples = config_data.get("examples", [])
        if examples:
            user_prompt = examples[0].get("user_input", "테스트 프롬프트")
            print(f"\n[샘플 예제 자동 입력]: {user_prompt}")
        else:
            print("\n설정 파일에 샘플 예제가 없어 기본 샘플을 사용합니다.")
            user_prompt = "파이썬 크롤링 코드 짜줘"
            print(f"[기본 샘플 입력]: {user_prompt}")
    else:
        user_prompt = input("\n보강하고 싶은 짧은 프롬프트를 입력하세요: ")
        if not user_prompt.strip():
            user_prompt = "파이썬 크롤링 코드 짜줘"
            print(f"입력값이 없어 기본 샘플을 사용합니다: {user_prompt}")
    
    print("\n[AI가 프롬프트를 보강 중입니다...]")
    result = generate_enhanced_prompt(user_prompt)
    
    print("\n" + "="*40)
    print(result)
    print("="*40)

import streamlit as st
import streamlit.components.v1 as components
import time
import json
import os
import subprocess
import re
import sys
import socket
import requests
import importlib
from pathlib import Path
from agent_google import generate_enhanced_prompt
from agent_local import generate_enhanced_prompt_local

# 워크스페이스 디렉토리 설정
WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# 안전한 rerun 함수
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# pulsedav 동적 경로 탐색 함수
def find_pulsedav_path():
    curr = Path(__file__).resolve().parent
    # 상위 디렉토리로 순차적으로 검색하며 BerePi 디렉토리 하위의 pulsedav 경로 탐색
    for parent in [curr] + list(curr.parents):
        # BerePi/apps/tinyGW/pulsedav 경로 확인
        if parent.name == "BerePi":
            target = parent / "apps" / "tinyGW" / "pulsedav"
            if target.exists() and (target / "pulsedav.py").exists():
                return target.resolve()
        target = parent / "apps" / "tinyGW" / "pulsedav"
        if target.exists() and (target / "pulsedav.py").exists():
            return target.resolve()
    return None

# 히스토리 파일 설정
HISTORY_FILE = Path("history_prompt.txt")

def load_prompt_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                # 줄바꿈 기준으로 읽어오되 빈 줄은 제외
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception:
            return []
    return []

def save_prompt_history(history):
    try:
        # 최근 1000개만 유지하여 저장
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for item in history[-1000:]:
                f.write(f"{item}\n")
    except Exception:
        pass

# pulsedav 모듈 로드 함수 (동적 경로 지원)
def get_pulsedav_module(path_str):
    if not path_str:
        return None
    p = Path(path_str)
    if p.exists():
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
        try:
            # 이미 임포트되어 있다면 리로드, 아니면 신규 임포트
            if "pulsedav" in sys.modules:
                return importlib.reload(sys.modules["pulsedav"])
            else:
                return importlib.import_module("pulsedav")
        except Exception:
            return None
    return None

# 페이지 설정
st.set_page_config(page_title="Persona Agent", page_icon="🤖", layout="wide")

st.title("🤖 AI Persona Agent (Pre-processing)")
st.caption("사용자의 프롬프트를 입력받고 에이전트의 응답을 확인 및 시스템 상태를 모니터링하는 UI입니다.")

# 페르소나 디렉토리 설정
PERSONA_DIR = Path(__file__).parent / "persona"
PERSONA_DIR.mkdir(exist_ok=True)

def get_persona_files():
    files = list(PERSONA_DIR.glob("*.json"))
    return [f.name for f in files] if files else ["persona_config.json"]

# 세션 상태 초기화 (AttributeError 방지를 위해 상단 배치)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 어떤 도움이 필요하신가요?"}
    ]

if "prompt_history" not in st.session_state:
    st.session_state.prompt_history = load_prompt_history()

# 사이드바 구성
with st.sidebar:
    st.header("⚙️ 설정 (Settings)")
    
    # 모델 제공자 선택
    provider = st.radio("AI 모델 제공자 선택", ["Google Gemini", "Local (Ollama)"], index=1)
    st.divider()
    
    if provider == "Google Gemini":
        # API 키 입력창
        api_key = st.text_input("Google Gemini API Key", type="password", placeholder="AIzaSy...")
        if st.button("API 키 유효성 테스트"):
            if not api_key:
                st.warning("API 키를 먼저 입력해주세요.")
            else:
                with st.spinner("테스트 중..."):
                    from google import genai
                    try:
                        client = genai.Client(api_key=api_key.strip())
                        client.models.generate_content(model="gemini-2.5-flash", contents="Hello")
                        st.success("API 키가 정상적으로 동작합니다! ✅")
                    except Exception as e:
                        st.error(f"유효하지 않은 API 키입니다 ❌\n{e}")
    else:
        # 로컬 모델 다운로드 및 설정
        st.subheader("📥 로컬 모델 관리")
        
        # 로컬에 설치된 Ollama 모델 목록 가져오기
        def get_local_ollama_models():
            try:
                res = requests.get("http://localhost:11434/api/tags", timeout=2)
                if res.status_code == 200:
                    return [m["name"] for m in res.json().get("models", [])]
            except:
                pass
            return []
            
        local_models = get_local_ollama_models()
        if local_models:
            ollama_target_model = st.selectbox("사용할 로컬 모델 선택", local_models, help="로컬에 이미 다운로드된 모델 중 하나를 선택하세요.")
        else:
            ollama_target_model = st.text_input("사용할 로컬 모델명", value="gemma4:e4b", help="로컬 모델이 감지되지 않습니다. 직접 입력하거나 아래에서 다운로드하세요.")
            st.warning("⚠️ 로컬에 설치된 모델이 없습니다. 아래에서 모델을 먼저 다운로드해 주세요.")
            
        ollama_exec_path = st.text_input("Ollama 실행 파일 경로", value="ollama", help="기본값 'ollama'가 작동하지 않으면 전체 경로(예: /usr/local/bin/ollama)를 입력하세요.")
        if st.button("Ollama 서버 시작 (Serve)"):
            with st.spinner("Ollama 서버를 백그라운드에서 시작하는 중..."):
                try:
                    # 백그라운드 프로세스로 실행
                    subprocess.Popen([ollama_exec_path, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    st.success("Ollama 서버 시작 명령을 보냈습니다. 잠시 후 다시 시도해 보세요.")
                except Exception as e:
                    st.error(f"서버 시작 실패: {e}")
        st.divider()
        st.markdown("**신규 모델 다운로드 (Pull)**")
        recommended_models = [
            "gemma4:e2b (Edge 2B)", "gemma4:e4b (Edge 4B)", "gemma4:26b (MoE)", "gemma4:31b (Dense)",
            "qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b", "qwen2.5:72b"
        ]
        selected_rec = st.selectbox("추천 모델 목록에서 선택", ["직접 입력"] + recommended_models)
        
        default_dl_name = ""
        if selected_rec != "직접 입력":
            default_dl_name = selected_rec.split(" ")[0]
            
        dl_model_name = st.text_input("다운로드할 모델명", value=default_dl_name, placeholder="예: gemma4:e4b")
        dl_model_path = st.text_input("Model Download Path (선택사항)", help="입력 시 OLLAMA_MODELS 환경변수로 적용됩니다.")
        
        # 현재 적용 중인 경로 표시
        current_path = dl_model_path if dl_model_path else os.environ.get("OLLAMA_MODELS", "~/.ollama/models (기본값)")
        st.caption(f"📂 현재 모델 저장 위치: `{current_path}`")
        
        col_dl1, col_dl2 = st.columns([1, 1])
        with col_dl1:
            pull_clicked = st.button("로컬 모델 다운로드 (Pull)", use_container_width=True)
        with col_dl2:
            stop_clicked = st.button("다운로드 중단", use_container_width=True)
            
        if pull_clicked:
            if not dl_model_name:
                st.warning("다운로드할 모델명을 입력해주세요.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                try:
                    # Ollama API를 사용하여 스트리밍 방식으로 진행률 수신
                    response = requests.post(
                        "http://localhost:11434/api/pull",
                        json={"name": dl_model_name},
                        stream=True,
                        timeout=None
                    )
                    
                    for line in response.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            
                            # API 에러 체크
                            if "error" in chunk:
                                st.error(f"Ollama 에러: {chunk['error']}")
                                break
                                
                            status = chunk.get("status", "")
                            completed = chunk.get("completed", 0)
                            total = chunk.get("total", 0)
                            
                            if total > 0:
                                progress = completed / total
                                progress_bar.progress(progress, text=f"다운로드 중: {status} ({progress*100:.1f}%)")
                            else:
                                status_text.text(f"현재 상태: {status}")
                                # 진행바가 0인 상태에서 텍스트만 갱신
                                progress_bar.progress(0, text=f"준비 중: {status}")
                                
                    st.success(f"'{dl_model_name}' 다운로드 및 준비 완료! ✅")
                    status_text.empty()
                except Exception as e:
                    st.error(f"다운로드 중 오류 발생: {e}\nOllama 서버가 실행 중인지 확인해 주세요.")

    st.divider()
    st.subheader("🛠️ 시스템 설정")
    
    # pulsedav 경로 자동 탐색
    detected_pulsedav = find_pulsedav_path()
    default_pulsedav_path = str(detected_pulsedav) if detected_pulsedav else "/Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav"
    
    pulsedav_path_input = st.text_input(
        "pulsedav 모듈 경로", 
        value=default_pulsedav_path,
        help="pulsedav 모듈이 위치한 폴더의 전체 경로를 입력하세요. 상위 디렉토리에서 검색된 경로가 자동으로 감지되어 설정됩니다."
    )
    st.divider()
    st.subheader("🎭 페르소나 관리")
    # 페르소나 파일 선택
    persona_files = get_persona_files()
    selected_file = st.selectbox("페르소나 파일 선택", persona_files)
    
    # 선택된 페르소나 파일 로드
    file_path = PERSONA_DIR / selected_file
    config_data = {}
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")
    else:
        config_data = {
            "persona": "기본 페르소나",
            "guidelines": ["가이드라인 1", "가이드라인 2"],
            "output_format": "출력 형식",
            "examples": []
        }
    
    # 폼(Form)을 통한 페르소나 내용 수정 및 저장
    with st.form("persona_form"):
        edited_persona = st.text_area("Persona", value=config_data.get("persona", ""), height=100)
        guidelines_text = "\n".join(config_data.get("guidelines", []))
        edited_guidelines = st.text_area("Guidelines (줄바꿈으로 구분)", value=guidelines_text, height=150)
        edited_output_format = st.text_area("Output Format", value=config_data.get("output_format", ""), height=150)
        
        st.divider()
        st.write("저장 설정")
        save_file_name = st.text_input("저장할 파일명 (.json)", value=selected_file)
        
        submit_button = st.form_submit_button("설정 저장")
        if submit_button:
            new_config = {
                "persona": edited_persona,
                "guidelines": [g.strip() for g in edited_guidelines.split("\n") if g.strip()],
                "output_format": edited_output_format,
                "examples": config_data.get("examples", [])
            }
            save_path = PERSONA_DIR / save_file_name
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, ensure_ascii=False, indent=4)
                st.success(f"{save_file_name} 저장 완료!")
                config_data = new_config
            except Exception as e:
                st.error(f"저장 실패: {e}")

# 전체 탭 구성
tab_chat, tab_system = st.tabs(["💬 프롬프트 보강", "🖥️ 시스템 상태"])

with tab_chat:
    # JS를 통한 Arrow Up/Down 히스토리 연동 (상단에서 로드)
    history_json = json.dumps(st.session_state.prompt_history)
    js_code = f"""
    <script>
    (function() {{
        const history = {history_json};
        let historyIndex = history.length;
        const doc = window.parent.document;
        
        function setNativeValue(element, value) {{
            const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            const prototype = Object.getPrototypeOf(element);
            const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, "value") ? Object.getOwnPropertyDescriptor(prototype, "value").set : null;
            
            if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {{
                prototypeValueSetter.call(element, value);
            }} else {{
                valueSetter.call(element, value);
            }}
            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}

        function onKeyDown(e) {{
            const chatInput = e.target;
            if (chatInput.tagName !== 'TEXTAREA') return;
            if (chatInput.getAttribute('data-testid') !== 'stChatInputTextArea') return;

            if (e.key === 'ArrowUp') {{
                if (historyIndex > 0) {{
                    historyIndex--;
                    setNativeValue(chatInput, history[historyIndex]);
                }}
                e.preventDefault();
            }} else if (e.key === 'ArrowDown') {{
                if (historyIndex < history.length - 1) {{
                    historyIndex++;
                    setNativeValue(chatInput, history[historyIndex]);
                }} else if (historyIndex === history.length - 1) {{
                    historyIndex = history.length;
                    setNativeValue(chatInput, '');
                }}
                e.preventDefault();
            }}
        }}

        function attach() {{
            const chatInput = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (chatInput) {{
                if (chatInput._historyListener) return; // 이미 연결됨
                
                // 새 리스너 등록
                chatInput._historyListener = onKeyDown;
                chatInput.addEventListener('keydown', onKeyDown);
                
                // 처음 연결될 때만 인덱스를 끝으로 설정
                historyIndex = history.length;
            }}
        }}

        // 초기 실행 및 주기적 감시
        setTimeout(attach, 100);
        setInterval(attach, 1000);
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)

    # Workspace 파일 관리 접히는 표시창
    with st.expander("📁 Workspace 파일 관리 및 업로드", expanded=False):
        st.markdown("##### 📥 신규 파일 업로드")
        uploaded_file = st.file_uploader(
            "업로드할 파일을 선택하세요. 업로드된 파일은 `workspace` 디렉토리에 저장됩니다.", 
            accept_multiple_files=False, 
            key="workspace_file_uploader"
        )
        if uploaded_file is not None:
            save_path = WORKSPACE_DIR / uploaded_file.name
            try:
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"파일 업로드 성공: `{uploaded_file.name}` ✅")
                safe_rerun()
            except Exception as e:
                st.error(f"파일 저장 실패: {e}")
        
        st.divider()
        st.markdown("##### 📂 업로드된 파일 목록 및 관리")
        # .gitkeep 파일은 목록에서 제외
        ws_files = [f.name for f in WORKSPACE_DIR.iterdir() if f.is_file() and f.name != ".gitkeep"]
        if ws_files:
            selected_ws_file = st.selectbox(
                "관리할 파일을 선택하세요", 
                sorted(ws_files), 
                key="workspace_file_selector"
            )
            st.session_state.active_workspace_file = selected_ws_file
            
            col_ws_info, col_ws_del = st.columns([3, 1])
            file_full_path = WORKSPACE_DIR / selected_ws_file
            
            # 파일 정보 출력
            if file_full_path.exists():
                file_size_kb = file_full_path.stat().st_size / 1024
                with col_ws_info:
                    st.info(f"📍 **경로**: `{file_full_path}`\n\n⚖️ **크기**: `{file_size_kb:.2f} KB`")
                with col_ws_del:
                    if st.button("🗑️ 파일 삭제", use_container_width=True, key="workspace_file_delete"):
                        try:
                            file_full_path.unlink()
                            st.success(f"파일 삭제 완료: `{selected_ws_file}` 🗑️")
                            if "active_workspace_file" in st.session_state:
                                del st.session_state.active_workspace_file
                            safe_rerun()
                        except Exception as e:
                            st.error(f"파일 삭제 실패: {e}")
        else:
            st.info("현재 workspace 디렉토리에 파일이 없습니다. 위에 파일을 드래그하여 업로드해 주세요.")
            if "active_workspace_file" in st.session_state:
                del st.session_state.active_workspace_file
            
    # 대화 및 명령 대상 파일 지정
    include_file_in_prompt = False
    if "active_workspace_file" in st.session_state and st.session_state.active_workspace_file:
        active_file = st.session_state.active_workspace_file
        include_file_in_prompt = st.checkbox(
            f"📄 선택된 파일 `{active_file}`을(를) AI 프롬프트 명령 대상으로 포함", 
            value=False,
            help="체크 시 파일 내용이 AI에게 전달되며, 프롬프트를 통해 AI에게 '열기/읽기', '삭제', '새로운 이름으로 저장'을 직접 명령할 수 있습니다."
        )
            
    st.divider()

    # 기존 대화 내용 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("프롬프트를 입력하세요 (화살표 ↑ 키로 이전 기록 불러오기 가능)"):
        # 히스토리에 추가 (최대 1000개 유지, 중복 연속 입력 방지)
        if not st.session_state.prompt_history or st.session_state.prompt_history[-1] != prompt:
            st.session_state.prompt_history.append(prompt)
            if len(st.session_state.prompt_history) > 1000:
                st.session_state.prompt_history.pop(0)
            # 로컬 파일에 즉시 저장
            save_prompt_history(st.session_state.prompt_history)

        # 사용자 메시지 출력 및 저장
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 에이전트 응답 처리
        start_time = time.time()
        
        # 워크스페이스 파일 명령 및 컨텍스트 결합
        actual_prompt = prompt
        if include_file_in_prompt and "active_workspace_file" in st.session_state and st.session_state.active_workspace_file:
            active_file = st.session_state.active_workspace_file
            selected_file_content = ""
            file_full_path = WORKSPACE_DIR / active_file
            try:
                if file_full_path.exists():
                    with open(file_full_path, "r", encoding="utf-8", errors="ignore") as f:
                        selected_file_content = f.read()
                else:
                    selected_file_content = "<오류: 파일이 존재하지 않습니다.>"
            except Exception as e:
                selected_file_content = f"<오류: 파일을 읽을 수 없습니다: {e}>"

            workspace_instruction = f"""
[SYSTEM NOTICE: WORKSPACE FILE INSTRUCTION]
현재 사용자가 선택하여 업로드/조회 중인 Workspace 파일 정보:
- 파일명: {active_file}
- 파일 경로: {file_full_path}

[파일 본문 내용]
---
{selected_file_content}
---

[시스템 액션 가이드라인]
사용자가 이 파일에 대해 '열기/읽기', '삭제', '새로운 이름으로 저장' 등을 명령할 경우, 대화를 자연스럽게 진행하면서 동시에 답변 가장 마지막 부분에 정확히 아래의 시스템 명령어 블록을 포함해 주세요:
1. 파일 '삭제' 시:
[SYSTEM_ACTION: DELETE {active_file}]

2. '새로운 이름으로 저장' 또는 '수정/가공하여 다른 이름으로 저장' 시:
[SYSTEM_ACTION: SAVE_AS <원하는_새로운_파일명>]
<파일에 작성될 최종 텍스트 내용만을 그대로 출력>
[/SYSTEM_ACTION]

3. 파일 '열기' 나 '읽기' 시에는 단순히 위 제공된 [파일 본문 내용]을 바탕으로 설명하거나 답변을 생성하면 됩니다.
"""
            actual_prompt = f"{workspace_instruction}\n\n사용자 프롬프트:\n{prompt}"

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("AI가 프롬프트를 분석하고 보강 중입니다..."):
                if provider == "Google Gemini":
                    target_model = "gemini-2.5-flash"
                    actual_reply = generate_enhanced_prompt(
                        user_input=actual_prompt,
                        api_key=api_key,
                        config_data=config_data
                    )
                else:
                    target_model = ollama_target_model
                    actual_reply = generate_enhanced_prompt_local(
                        user_input=actual_prompt,
                        model_name=ollama_target_model,
                        config_data=config_data
                    )
            
            # 시스템 명령 태그 파싱 및 정제
            system_action_msg = ""
            clean_reply = actual_reply
            
            # 1. DELETE 명령어 파싱 및 실행
            if "[SYSTEM_ACTION: DELETE " in actual_reply:
                try:
                    parts = actual_reply.split("[SYSTEM_ACTION: DELETE ")
                    if len(parts) > 1:
                        target_fn = parts[1].split("]")[0].strip()
                        target_path = WORKSPACE_DIR / target_fn
                        if target_path.exists():
                            target_path.unlink()
                            system_action_msg = f"🗑️ **시스템 액션 성공**: `{target_fn}` 파일을 성공적으로 삭제했습니다!"
                            # 세션 상태에서도 제거
                            if "active_workspace_file" in st.session_state and st.session_state.active_workspace_file == target_fn:
                                del st.session_state.active_workspace_file
                        else:
                            system_action_msg = f"⚠️ **시스템 액션 실패**: 삭제하려는 파일 `{target_fn}`이(가) 존재하지 않습니다."
                        
                        clean_reply = parts[0] + (parts[1].split("]")[1] if "]" in parts[1] else "")
                except Exception as ex:
                    system_action_msg = f"❌ **시스템 액션 실패 (삭제 중 에러)**: {ex}"
            
            # 2. SAVE_AS 명령어 파싱 및 실행
            elif "[SYSTEM_ACTION: SAVE_AS " in actual_reply:
                try:
                    parts = actual_reply.split("[SYSTEM_ACTION: SAVE_AS ")
                    if len(parts) > 1:
                        header_and_body = parts[1].split("]")
                        target_fn = header_and_body[0].strip()
                        rest = "]".join(header_and_body[1:])
                        
                        body = rest.split("[/SYSTEM_ACTION]")[0].strip()
                        target_path = WORKSPACE_DIR / target_fn
                        
                        WORKSPACE_DIR.mkdir(exist_ok=True)
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(body)
                            
                        system_action_msg = f"💾 **시스템 액션 성공**: `{target_fn}` 파일에 데이터를 성공적으로 저장했습니다!"
                        
                        clean_reply = parts[0] + (rest.split("[/SYSTEM_ACTION]")[1] if "[/SYSTEM_ACTION]" in rest else "")
                except Exception as ex:
                    system_action_msg = f"❌ **시스템 액션 실패 (저장 중 에러)**: {ex}"
                
            full_response = ""
            lines = clean_reply.split('\n')
            for i, line in enumerate(lines):
                words = line.split(' ')
                for word in words:
                    full_response += word + " "
                    time.sleep(0.005)
                    message_placeholder.markdown(full_response + "▌")
                if i < len(lines) - 1:
                    full_response += "\n"
            
            message_placeholder.markdown(full_response)
            
            # 실행된 시스템 액션 알림 출력
            if system_action_msg:
                st.info(system_action_msg)
                full_response += f"\n\n***\n{system_action_msg}"
            
            # 처리 시간 및 모델 정보 표시
            elapsed_time = time.time() - start_time
            st.caption(f"⏱️ {elapsed_time:.2f}s | 🤖 {target_model}")
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})


with tab_system:
    def get_gpu_info():
        info = {"gpu_desc": "알 수 없음", "total_vram": "알 수 없음", "vram_usage": "알 수 없음"}
        
        # 1. Linux NVIDIA GPU 확인 (nvidia-smi 명령어 지원 여부)
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"], 
                capture_output=True, 
                text=True,
                check=False
            )
            if res.returncode == 0:
                lines = res.stdout.strip().split('\n')
                if lines and lines[0]:
                    parts = [p.strip() for p in lines[0].split(',')]
                    if len(parts) >= 3:
                        gpu_name = parts[0]
                        used_mib = float(parts[1])
                        total_mib = float(parts[2])
                        used_gb = used_mib / 1024
                        total_gb = total_mib / 1024
                        percent = (used_mib / total_mib) * 100 if total_mib > 0 else 0.0
                        
                        info["gpu_desc"] = f"NVIDIA {gpu_name}"
                        info["total_vram"] = f"{total_gb:.2f} GB"
                        info["vram_usage"] = f"{used_gb:.2f} GB / {total_gb:.2f} GB ({percent:.1f}%)"
                        return info
        except Exception:
            pass

        # 2. Mac Displays & Displays & VRAM 확인 (기존 fallback)
        try:
            sp = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True)
            if sp.returncode == 0:
                out = sp.stdout
                chipset = re.search(r"Chipset Model:\s*(.*)", out)
                vram = re.search(r"VRAM \(Total\):\s*(.*)", out)
                if chipset:
                    info["gpu_desc"] = f"{chipset.group(1)} (Total VRAM: {vram.group(1) if vram else 'N/A'})"
                    
                ioreg = subprocess.run(["ioreg", "-l"], capture_output=True, text=True)
                free_bytes_match = re.search(r'"vramFreeBytes"=(\d+)', ioreg.stdout)
                total_mb_match = re.search(r'"VRAM,totalMB"=(\d+)', ioreg.stdout)
                
                if free_bytes_match and total_mb_match:
                    free_bytes = int(free_bytes_match.group(1))
                    total_mb = int(total_mb_match.group(1))
                    total_bytes = total_mb * 1024 * 1024
                    used_bytes = total_bytes - free_bytes
                    percent = (used_bytes / total_bytes) * 100
                    
                    used_gb = used_bytes / (1024*1024*1024)
                    total_gb = total_mb / 1024
                    info["vram_usage"] = f"{used_gb:.2f} GB / {total_gb:.2f} GB ({percent:.1f}%)"
                    return info
        except Exception:
            pass
        return info

    def get_ollama_version():
        try:
            res = subprocess.run([ollama_exec_path, "--version"], capture_output=True, text=True)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return "설치되지 않음 (또는 실행 불가)"

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '알 수 없음'
        finally:
            s.close()
        return IP
        
    def get_public_ip():
        try:
            return requests.get('https://api.ipify.org', timeout=3).text
        except Exception:
            return "알 수 없음"

    # Streamlit 1.37 이상부터 지원하는 fragment 기능으로 시스템 모니터링 부분만 30초마다 갱신
    @st.fragment(run_every="30s")
    def render_system_status():
        st.subheader("📊 시스템 및 로컬 환경 모니터링")
        col1, col2, col3 = st.columns(3)
        
        # 프리미엄 테마 대응형 컴팩트 메트릭 헬퍼 함수
        def sys_metric(label, value):
            st.markdown(f"""
            <div style="
                background: var(--background-secondary-color, rgba(128, 128, 128, 0.05));
                border-left: 4px solid #6366F1;
                padding: 8px 12px;
                border-radius: 6px;
                margin-bottom: 10px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            ">
                <div style="font-size: 0.75rem; color: var(--text-color, #6B7280); font-weight: 600; opacity: 0.7; letter-spacing: 0.5px;">{label}</div>
                <div style="font-size: 0.88rem; color: var(--text-color, #1F2937); font-weight: 700; margin-top: 4px; word-break: break-word; line-height: 1.35;">{value}</div>
            </div>
            """, unsafe_allow_html=True)

        gpu_info = get_gpu_info()
        with col1:
            sys_metric("GPU 종류 (개수 및 모델)", gpu_info["gpu_desc"])
            sys_metric("현재 GPU 메모리 사용량", gpu_info["vram_usage"])
            
        with col2:
            sys_metric("Ollama 구동 버전", get_ollama_version())
            
        with col3:
            sys_metric("Local IP", get_local_ip())
            sys_metric("Public IP", get_public_ip())
            
        st.divider()
        st.subheader("🖥️ 시스템 상세 내용 (pulsedav/sender.py)")
        
        # 입력된 경로로 pulsedav 동적 로드
        pulsedav_mod = get_pulsedav_module(pulsedav_path_input)
        
        if pulsedav_mod is not None:
            try:
                # pulsedav 내부 로직을 통해 시스템 스냅샷 및 마크다운 생성
                settings = pulsedav_mod.load_settings()
                snapshot = pulsedav_mod.collect_snapshot(settings)
                markdown = pulsedav_mod.format_markdown(settings, snapshot, is_first_boot_message=False)
                st.markdown(markdown)
            except Exception as e:
                st.error(f"pulsedav 정보를 불러오는 중 오류 발생: {e}")
        else:
            st.error(f"pulsedav 모듈을 불러오지 못했습니다. 경로를 확인해주세요: {pulsedav_path_input}")

    render_system_status()

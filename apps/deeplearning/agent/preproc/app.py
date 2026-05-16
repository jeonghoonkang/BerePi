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
from pathlib import Path
from agent_google import generate_enhanced_prompt
from agent_local import generate_enhanced_prompt_local

# pulsedav 경로 추가 (시스템 탭에서 사용)
sys.path.append("/Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav")
try:
    import pulsedav
except ImportError:
    pulsedav = None

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
    # 세션 상태에 대화 기록 및 프롬프트 히스토리 저장
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "안녕하세요! 어떤 도움이 필요하신가요?"}
        ]

    if "prompt_history" not in st.session_state:
        st.session_state.prompt_history = []

    # 기존 대화 내용 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("프롬프트를 입력하세요 (화살표 ↑ 키로 이전 기록 불러오기 가능)"):
        # 히스토리에 추가 (최대 100개 유지, 중복 연속 입력 방지)
        if not st.session_state.prompt_history or st.session_state.prompt_history[-1] != prompt:
            st.session_state.prompt_history.append(prompt)
            if len(st.session_state.prompt_history) > 100:
                st.session_state.prompt_history.pop(0)

        # 사용자 메시지 출력 및 저장
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 에이전트 응답 처리
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            with st.spinner("AI가 프롬프트를 분석하고 보강 중입니다..."):
                if provider == "Google Gemini":
                    actual_reply = generate_enhanced_prompt(
                        user_input=prompt,
                        api_key=api_key,
                        config_data=config_data
                    )
                else:
                    actual_reply = generate_enhanced_prompt_local(
                        user_input=prompt,
                        model_name=ollama_target_model,
                        config_data=config_data
                    )
                
            full_response = ""
            lines = actual_reply.split('\n')
            for i, line in enumerate(lines):
                words = line.split(' ')
                for word in words:
                    full_response += word + " "
                    time.sleep(0.02)
                    message_placeholder.markdown(full_response + "▌")
                if i < len(lines) - 1:
                    full_response += "\n"
            
            message_placeholder.markdown(full_response)
            
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # JS를 통한 Arrow Up/Down 히스토리 연동
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

        function attachHistory() {{
            const chatInput = doc.querySelector('textarea[data-testid="stChatInputTextArea"]');
            if (!chatInput) return;
            
            if (chatInput.hasAttribute('data-history-active')) return;
            chatInput.setAttribute('data-history-active', 'true');
            
            chatInput.addEventListener('keydown', function(e) {{
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
            }});
        }}

        // 정기적으로 체크하여 엘리먼트가 새로 생기면 바인딩
        setInterval(attachHistory, 500);
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)

with tab_system:
    def get_mac_gpu_info():
        info = {"gpu_desc": "알 수 없음", "total_vram": "알 수 없음", "vram_usage": "알 수 없음"}
        try:
            sp = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True)
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
        
        gpu_info = get_mac_gpu_info()
        with col1:
            st.metric("GPU 종류 (개수 및 모델)", gpu_info["gpu_desc"])
            st.metric("현재 GPU 메모리 사용량", gpu_info["vram_usage"])
            
        with col2:
            st.metric("Ollama 구동 버전", get_ollama_version())
            
        with col3:
            st.metric("Local IP", get_local_ip())
            st.metric("Public IP", get_public_ip())
            
        st.divider()
        st.subheader("🖥️ 시스템 상세 내용 (pulsedav/sender.py)")
        if pulsedav is not None:
            try:
                # pulsedav 내부 로직을 통해 시스템 스냅샷 및 마크다운 생성
                settings = pulsedav.load_settings()
                snapshot = pulsedav.collect_snapshot(settings)
                markdown = pulsedav.format_markdown(settings, snapshot, is_first_boot_message=False)
                st.markdown(markdown)
            except Exception as e:
                st.error(f"pulsedav 정보를 불러오는 중 오류 발생: {e}")
        else:
            st.error("pulsedav 모듈을 불러오지 못했습니다. 경로를 확인해주세요.")

    render_system_status()

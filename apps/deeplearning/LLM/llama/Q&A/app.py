import os
import time
import threading

import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


def rerun() -> None:
    """Compatibility helper to rerun the Streamlit script."""
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun()


def display_gpu_status(tokenizer=None) -> None:
    """Display current GPU and model info at startup."""
    try:
        import torch

        # 애플 실리콘 MPS 지원 확인
        if torch.backends.mps.is_available():
            st.info("Apple Silicon GPU (MPS) available")
            try:
                # MPS 디바이스 정보 표시
                device = torch.device("mps")
                st.info(f"Using device: {device}")
            except Exception as e:
                st.warning(f"MPS device error: {e}")
        elif torch.cuda.is_available():
            gpu_names = [f"{i}: {torch.cuda.get_device_name(i)}" for i in range(torch.cuda.device_count())]
            st.info("GPU available: " + ", ".join(gpu_names))

            mem_info = []
            for i in range(torch.cuda.device_count()):
                total = torch.cuda.get_device_properties(i).total_memory // (1024 ** 2)
                allocated = torch.cuda.memory_allocated(i) // (1024 ** 2)
                mem_info.append(f"{i}: {allocated}MB/{total}MB")
            st.info("GPU memory usage: " + ", ".join(mem_info))
        else:
            st.info("GPU not available, using CPU")
    except Exception as exc:  # pragma: no cover - GPU inspection can fail
        st.warning(f"Could not determine GPU status: {exc}")

    if tokenizer is not None:
        try:
            st.info(f"Max input tokens: {getattr(tokenizer, 'model_max_length', 'unknown')}")
        except Exception:  # pragma: no cover - tokenizer may be malformed
            pass

st.set_page_config(page_title="Llama Q&A", page_icon="🦙")

st.title("🦙 Llama 기반 Q&A 데모")

# 사이드바에 모델 선택 옵션 추가
st.sidebar.header("모델 설정")
model_option = st.sidebar.selectbox(
    "모델 선택",
    [
        "NousResearch/Llama-2-7b-chat-hf",
        "NousResearch/Llama-2-13b-chat-hf",
        "microsoft/DialoGPT-medium",
        "gpt2",
        "distilgpt2"
    ],
    index=0
)

# 모델 파라미터 설정
st.sidebar.header("생성 파라미터")
max_length = st.sidebar.slider("최대 길이", 100, 2048, 512)
temperature = st.sidebar.slider("Temperature", 0.1, 2.0, 0.7)
top_p = st.sidebar.slider("Top-p", 0.1, 1.0, 0.9)
do_sample = st.sidebar.checkbox("샘플링 사용", value=True)


def download_model(model_name: str) -> None:
    """Download the model showing a simple progress bar."""
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        st.error("huggingface_hub is required to download models")
        st.stop()

    progress = st.progress(0)

    def _download():
        try:
            snapshot_download(repo_id=model_name, local_dir=model_name, resume_download=True)
        except Exception as exc:
            st.session_state.download_error = str(exc)

    thread = threading.Thread(target=_download)
    thread.start()
    pct = 0
    while thread.is_alive():
        pct = min(100, pct + 1)
        progress.progress(pct / 100.0)
        time.sleep(1)

    thread.join()
    progress.progress(1.0)
    if "download_error" in st.session_state:
        st.error("Failed to download model: " + st.session_state.download_error)
        st.stop()
    st.success("Download complete")


def ensure_model(model_name: str) -> None:
    """Ensure the model files are available. Auto download after 10s."""
    if os.path.isdir(model_name):
        return
    try:
        from huggingface_hub import hf_hub_download

        # check config and at least one weight file exists locally
        hf_hub_download(repo_id=model_name, filename="config.json", local_files_only=True)
        try:
            hf_hub_download(repo_id=model_name, filename="pytorch_model.bin", local_files_only=True)
        except Exception:
            hf_hub_download(repo_id=model_name, filename="pytorch_model.bin.index.json", local_files_only=True)
        return
    except Exception:
        pass

    if "prompt_time" not in st.session_state:
        st.session_state.prompt_time = time.time()

    elapsed = time.time() - st.session_state.prompt_time
    remaining = int(10 - elapsed)

    if "download_decision" not in st.session_state:
        st.session_state.download_decision = None

    if st.session_state.download_decision is None:
        st.warning(f"Model '{model_name}' not found. Download? (auto in {max(remaining,0)}s)")
        cols = st.columns(2)
        if cols[0].button("Download now"):
            st.session_state.download_decision = True
            rerun()

        if cols[1].button("Cancel"):
            st.session_state.download_decision = False
            st.stop()
        if remaining <= 0:
            st.session_state.download_decision = True
            rerun()
        else:
            time.sleep(1)
            rerun()

    elif st.session_state.download_decision:
        download_model(model_name)
    else:
        st.stop()


# 모델 로딩
MODEL_NAME = model_option
ensure_model(MODEL_NAME)


@st.cache_resource
def load_model(name: str):
    import torch
    
    # 토크나이저 로드 시 trust_remote_code=True 추가
    tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    
    # 패딩 토큰이 없으면 EOS 토큰을 패딩 토큰으로 설정
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    try:
        # 우선 로컬 파일만 사용하여 로드 시도
        model = AutoModelForCausalLM.from_pretrained(
            name,
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True,
        )
    except FileNotFoundError:
        # 로컬 파일이 누락된 경우 자동으로 다운로드
        st.warning("모델 파일이 없어 다운로드를 진행합니다.")
        with st.spinner("모델 다운로드 중..."):
            model = AutoModelForCausalLM.from_pretrained(
                name,
                device_map="auto",
                trust_remote_code=True,
            )
    except Exception:
        # 기타 오류는 다시 시도하여 처리
        with st.spinner("모델 다운로드 중..."):
            model = AutoModelForCausalLM.from_pretrained(
                name,
                device_map="auto",
                trust_remote_code=True,
            )

    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

    return generator


# 모델 로드
with st.spinner("모델 로딩 중..."):
    generator = load_model(MODEL_NAME)
    display_gpu_status(generator.tokenizer)

# 모델별 프롬프트 포맷팅 함수
def format_prompt(user_input: str, model_name: str) -> str:
    """모델별 채팅 형식으로 프롬프트 포맷팅"""
    if "llama" in model_name.lower():
        return f"""<s>[INST] {user_input} [/INST]"""
    elif "dialogpt" in model_name.lower():
        return f"Human: {user_input}\nAssistant:"
    else:
        return user_input

# 메인 인터페이스
st.header("💬 질문하기")

# 채팅 히스토리 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 히스토리 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("질문을 입력하세요"):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 어시스턴트 응답 생성
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        time_placeholder = st.empty()
        
        try:
            start_time = time.time()
            with st.spinner("답변 생성 중..."):
                # 모델별 채팅 형식으로 프롬프트 포맷팅
                formatted_prompt = format_prompt(prompt, MODEL_NAME)
                
                response = generator(
                    formatted_prompt, 
                    max_length=max_length, 
                    do_sample=do_sample,
                    temperature=temperature,
                    top_p=top_p,
                    pad_token_id=generator.tokenizer.eos_token_id
                )
                
                # 응답에서 프롬프트 부분 제거하고 답변만 추출
                full_response = response[0]["generated_text"]
                answer = full_response[len(formatted_prompt):].strip()
                
                # 답변을 스트리밍으로 표시
                full_response_text = ""
                for chunk in answer.split():
                    full_response_text += chunk + " "
                    message_placeholder.markdown(full_response_text + "▌")
                    time.sleep(0.05)
                message_placeholder.markdown(full_response_text)
            elapsed = time.time() - start_time
            time_placeholder.markdown(f"_(응답 시간: {elapsed:.2f}초)_")
                
        except Exception as exc:
            message_placeholder.error("답변 생성 중 오류가 발생했습니다.")
            with st.expander("오류 상세 보기"):
                st.exception(exc)
        else:
            # 어시스턴트 메시지 추가
            st.session_state.messages.append({"role": "assistant", "content": answer})

# 채팅 히스토리 초기화 버튼
if st.sidebar.button("채팅 히스토리 초기화"):
    st.session_state.messages = []
    st.rerun()

# 모델 정보 표시
st.sidebar.header("모델 정보")
st.sidebar.info(f"현재 모델: {MODEL_NAME}")
st.sidebar.info(f"토크나이저: {generator.tokenizer.__class__.__name__}")

# 사용법 안내
with st.expander("사용법"):
    st.markdown("""
    ### Llama Q&A 사용법
    
    1. **모델 선택**: 사이드바에서 원하는 Llama 모델을 선택하세요
    2. **파라미터 조정**: Temperature, Top-p 등을 조정하여 답변의 창의성을 조절하세요
    3. **질문 입력**: 채팅창에 질문을 입력하세요
    4. **답변 확인**: Llama가 생성한 답변을 확인하세요
    
    ### 팁
    - 더 큰 모델(13B, 70B)은 더 정확한 답변을 제공하지만 로딩 시간이 길어집니다
    - Temperature를 낮추면 더 일관된 답변을, 높이면 더 창의적인 답변을 얻을 수 있습니다
    - Apple Silicon Mac에서는 MPS 가속을 자동으로 사용합니다
    """) 
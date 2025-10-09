#Author: https://github.com/jeonghoonkang

import os
from huggingface_hub import snapshot_download
from typing import Optional

def download_gemma3_model(
    model_name: str,
    hf_token: Optional[str],
    local_dir: str
):
    """
    Hugging Face Hub에서 모델을 지정된 로컬 폴더에 명시적으로 다운로드합니다.
    """
    if not os.path.exists(local_dir):
        print(f"로컬 디렉토리 생성: {local_dir}")
        os.makedirs(local_dir)

    print(f"'{model_name}' 모델을 로컬에 다운로드 중...")
    
    # Hugging Face Hub에서 모델의 모든 파일을 다운로드합니다.
    snapshot_download(
        repo_id=model_name,
        local_dir=local_dir,
        token=hf_token, # 토큰은 gated repo 접근 시 필요합니다.
        allow_patterns=["*"], # 모든 파일 다운로드
    )
    print(f"다운로드 완료. 로컬 경로: {local_dir}")

# # 사용 예시 (다운로드를 원할 경우 주석 해제 후 실행)
MODEL_NAME = "google/gemma-3-27b-it"
LOCAL_MODEL_PATH = "/home/***/devel/model_down" # 원하는 로컬 경로 설정
HF_TOKEN = "******"

download_gemma3_model(
    model_name=MODEL_NAME,
    hf_token=HF_TOKEN,
    local_dir=LOCAL_MODEL_PATH
)

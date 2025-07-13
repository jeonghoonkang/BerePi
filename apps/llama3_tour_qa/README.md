# Llama 3로 한국 관광 Q&A

이 Streamlit 앱은 Meta의 Llama 3 모델을 사용하여 한국 여행에 관한 질문에 답합니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   pip install streamlit transformers huggingface_hub
   ```
   로컬에 Llama 3 모델 파일이 필요합니다. 환경 변수 `LLAMA3_MODEL`에 모델 폴더나 이름을 지정하세요.
2. 앱 실행
   ```bash
   streamlit run app.py
   ```

기본값으로 HuggingFace의 `meta-llama/Meta-Llama-3-8B-Instruct`를 불러옵니다.
모델 파일이 없으면 다운로드 여부를 묻고 10초 후 자동으로 다운로드를 시작하며,
진행 상황을 프로그레스 바로 표시합니다. 앱 시작 시 GPU 사용 가능 여부도 출력합니다.

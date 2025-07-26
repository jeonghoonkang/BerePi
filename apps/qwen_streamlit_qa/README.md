# Qwen으로 Q&A 데모

이 예제는 Alibaba의 Qwen 모델을 사용하여 간단한 질문/답변 데모를 실행하는 Streamlit 앱입니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   pip install streamlit transformers huggingface_hub
   ```
  환경 변수 `QWEN_MODEL`에 로컬 모델 경로 또는 HuggingFace 모델 이름을 지정할 수 있습니다.
  GGUF 모델을 사용할 경우 `QWEN_GGUF_MODEL` 환경 변수로 모델 파일 경로를 설정할 수 있습니다.
2. 앱 실행
   ```bash
   streamlit run app.py
   ```

기본적으로 `Qwen/Qwen1.5-7B-Chat` 모델을 사용하며, 로컬에 모델이 없으면 다운로드합니다.
사이드바의 **모델 선택** 메뉴에서 `Qwen1.5-1.8B-Chat (GGUF)` 모델을 선택해 사용할 수도 있습니다.
GGUF 모델을 사용할 때는 `llama_cpp` 패키지가 필요합니다.
앱을 실행하면 화면 상단에 GPU 사용 가능 여부가 표시되고, 이어서 현재 GPU 메모리 사용량과
모델이 지원하는 최대 입력 토큰 수가 함께 보여집니다.
모델 로딩 시 `device_map="auto"` 옵션을 사용하여 가용한 GPU가 자동으로 활용됩니다.

질문 입력창 옆에는 사람 이모지가, 답변 출력에는 귀여운 로봇 이모지가 표시됩니다.

### 오류 확인

모델 실행 중 문제가 발생하면 화면 하단에 오류 메시지와 함께 상세 내용을 볼 수 있는 창이 나타납니다.

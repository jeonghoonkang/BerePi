# Qwen과 OpenAI 두 모델로 Q&A 데모

이 예제는 하나의 Streamlit 웹페이지에서 Qwen 모델과 OpenAI API를 동시에 사용하여 질문/답변을 수행합니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   pip install streamlit transformers huggingface_hub openai
   ```
  환경 변수 `QWEN_MODEL`에 로컬 모델 경로 또는 HuggingFace 모델 이름을 지정할 수 있습니다.
  OpenAI API 키는 `OPENAI_API_KEY` 환경 변수 또는 `nocommit_key.txt` 파일을 통해 설정할 수 있습니다.
2. 앱 실행
   ```bash
   streamlit run app.py
   ```

기본적으로 Qwen1.5-7B-Chat 모델을 사용하며, 필요 시 다운로드 여부를 묻고 10초 후 자동으로 다운로드합니다.
화면은 좌우 두 영역으로 나뉘어 각각 Qwen과 OpenAI에 질문을 입력하고 결과를 확인할 수 있습니다.

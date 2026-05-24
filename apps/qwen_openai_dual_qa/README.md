# Qwen과 OpenAI 두 모델로 Q&A 데모

이 예제는 하나의 Streamlit 웹페이지에서 Qwen 모델과 OpenAI API를 동시에 사용하여 질문/답변을 수행합니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```
  환경 변수 `QWEN_MODEL`에 로컬 모델 경로 또는 HuggingFace 모델 이름을 지정할 수 있습니다.
  OpenAI API 키는 `OPENAI_API_KEY` 환경 변수 또는 `nocommit_key.txt` 파일을 통해 설정할 수 있습니다.

2. Streamlit 앱 실행
   ```bash
   streamlit run app.py
   ```

기본적으로 Qwen1.5-7B-Chat 모델을 사용하며, 필요 시 다운로드 여부를 묻고 10초 후 자동으로 다운로드합니다.
화면은 좌우 두 영역으로 나뉘어 각각 Qwen과 OpenAI에 질문을 입력하고 결과를 확인할 수 있습니다.

## API 실행

프롬프트를 API로 전달하고 JSON 응답을 받으려면 FastAPI 서버를 실행합니다.

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

요청 예시:

```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","prompt":"안녕하세요. 오늘 할 일을 정리해 주세요."}'
```

Qwen을 사용하려면 `provider`를 `qwen`으로 지정합니다.

```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"provider":"qwen","prompt":"라즈베리파이에서 온도 센서를 읽는 방법을 알려줘.","max_length":512}'
```

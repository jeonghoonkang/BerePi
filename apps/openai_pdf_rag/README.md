# OpenAI PDF RAG 데모

이 예제는 Streamlit을 이용하여 PDF 문서를 업로드하고, 문서 내용을 기반으로
질문에 답하는 간단한 RAG(Retrieval Augmented Generation) 웹앱입니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash
   pip install streamlit openai PyPDF2 numpy
   ```
   OpenAI API 키는 `OPENAI_API_KEY` 환경 변수 또는 `nocommit_key.txt` 파일을 통해
   설정할 수 있습니다.

2. 앱 실행
   ```bash
   streamlit run app.py
   ```

페이지에서 "PDF 내용 사용" 체크박스를 선택하면 업로드한 문서 내용을 기반으로
답변을 생성합니다. 체크하지 않으면 일반 OpenAI 대화와 동일하게 동작합니다.


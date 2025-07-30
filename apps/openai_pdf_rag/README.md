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

질문을 입력하면 첫 번째 영역에 기본 답변이 표시됩니다.
"답변 모드" 라디오 버튼을 "PDF 사용"으로 설정하면 두 번째 영역에
업로드한 문서를 활용한 답변이 출력됩니다.
세 번째 영역에는 추출된 PDF 내용이 그대로 보여집니다.

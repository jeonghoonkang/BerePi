# OpenAI PDF RAG 데모

이 예제는 Streamlit을 이용하여 한 개 이상의 PDF 문서를 업로드하고, 문서 내용
을 기반으로 질문에 답하는 간단한 RAG(Retrieval Augmented Generation) 웹앱입니다.

## 사용 방법

1. 필요한 패키지 설치
   ```bash

   pip install streamlit openai PyPDF2 numpy pandas fpdf
   ```
   OpenAI API 키는 `OPENAI_API_KEY` 환경 변수 또는 `nocommit.txt` 파일을 통해
   설정할 수 있습니다. Gemma 등 허깅페이스에서 접근 제한이 있는 모델을
   사용하려면 `HF_TOKEN` 환경 변수나 `hf_token.txt` 파일에 Hugging Face 토큰을
   제공해야 합니다.

2. 앱 실행
   ```bash
   streamlit run app.py
   ```

앱 상단에는 시스템에 설치된 GPU(개수 및 모델)와 선택한 AI 모델이 표시됩니다.
또한 질문 입력란 위에 가로줄을 넣어 영역을 구분합니다. OpenAI 모델 외에도
llama-3, mistral, gemma 등 OSS 모델을 선택할 수 있으며, 로컬에 모델이 없으면
다운로드 버튼이 나타나고 다운로드 후 파일 무결성을 검사합니다.

질문을 입력하면 첫 번째 영역에 기본 답변이 표시됩니다.

"답변 모드"를 "PDF 사용"으로 설정하면 두 번째 영역에 업로드한 여러 PDF
문서를 조합한 답변이 표시됩니다. 세 번째 영역에는 모든 PDF에서 추출한
원본 텍스트가 그대로 출력됩니다.

추가 기능
- 최근 100개까지의 질문과 답변을 메모리에 저장합니다.
- 답변 생성에 걸린 시간이 표시됩니다.
- 이전 질문과 답변을 선택해서 다시 볼 수 있는 드롭다운 메뉴가 제공됩니다.
- 저장된 모든 질문과 답변을 PDF 또는 엑셀 파일로 다운로드할 수 있습니다.

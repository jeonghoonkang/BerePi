# Image Preprocessing Streamlit App

실행:

```bash
pip install -r apps/image_box_touch_app/requirements.txt
streamlit run apps/image_box_touch_app/app.py
```

기능:

- 지정 디렉토리 재귀 스캔
- `jpg`, `jpeg`, `gif`, `png` 파일 검색
- 파일 개수, 총 용량, 현재 파일 메타데이터 표시
- 마우스 박스 선택 및 좌표 저장
- `지우기`, `남기기`, `자르기` 전처리
- 새 파일명에 시간과 동작 코드 추가 저장
- 디렉토리 전체 일괄 처리
- 버튼을 누를 때마다 한 장씩 처리

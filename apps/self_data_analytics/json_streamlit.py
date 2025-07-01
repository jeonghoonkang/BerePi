import streamlit as st
import json

# JSON 파일 열기
uploaded_file = st.file_uploader("JSON 파일을 업로드하세요", type="json")
if uploaded_file is not None:
    data = json.load(uploaded_file)
    st.write("JSON 데이터:", data)
    print(isinstance(data, dict))
    item_count = len(data)
    st.write(f"JSON 아이템 갯수: {item_count}")
    # 키워드 입력 (Streamlit 웹 화면에서 입력)
    keyword = st.text_input("검색할 키워드를 입력하세요")

    if keyword:
        if isinstance(data, dict):
            results = {k: v for k, v in data.items() if keyword in k or keyword in str(v)}
        elif isinstance(data, list):
            results = [item for item in data if isinstance(item, dict) and any(
                keyword in str(k) or keyword in str(v) for k, v in item.items())]
        else:
            results = "지원되지 않는 JSON 구조입니다."

        st.write("검색 결과:", results)
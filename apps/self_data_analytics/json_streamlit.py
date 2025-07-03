import streamlit as st
import json
import os

# 기본 파일 이름 설정
file_path = st.text_input("JSON 파일 경로", value="file_list.json")

data = None
if os.path.exists(file_path):
    # 기본 파일이 존재하면 버튼 하나로 바로 열 수 있게 함
    if st.button("오픈"):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            st.session_state['json_string'] = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            st.error(f"파일을 열 수 없습니다: {e}")
else:
    st.warning(f"{file_path} 파일이 존재하지 않습니다. 다른 파일을 선택하세요.")
    uploaded_file = st.file_uploader("JSON 파일을 업로드하세요", type="json")
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            st.session_state['json_string'] = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            st.error(f"업로드된 파일을 읽을 수 없습니다: {e}")


# 세션 상태에 저장된 JSON 문자열을 가져와서 편집 가능하도록 표시
json_string = st.session_state.get('json_string', '')
edited_json_string = st.text_area("JSON 데이터 편집", value=json_string, height=300)

if edited_json_string:
    try:
        data = json.loads(edited_json_string)
        item_count = len(data) if isinstance(data, (dict, list)) else 0
        st.write(f"JSON 아이템 갯수: {item_count}")
        # 키워드 입력
        keyword = st.text_input("검색할 키워드를 입력하세요")
        if keyword:
            if isinstance(data, dict):
                results = {k: v for k, v in data.items() if keyword in str(k) or keyword in str(v)}
            elif isinstance(data, list):
                results = [item for item in data if isinstance(item, dict) and any(keyword in str(k) or keyword in str(v) for k, v in item.items())]
            else:
                results = "지원되지 않는 JSON 구조입니다."
            st.write("검색 결과:", results)

        # 편집된 JSON 데이터를 파일로 저장
        if st.button("저장"):
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                st.success(f"{file_path} 파일로 저장했습니다.")
            except Exception as e:
                st.error(f"파일을 저장할 수 없습니다: {e}")

    except json.JSONDecodeError as e:
        st.error(f"JSON 구문 오류: {e}")

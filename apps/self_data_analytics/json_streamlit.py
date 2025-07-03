import streamlit as st
import json
import os
import tempfile
from webdav3.client import Client


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
                st.write(f"저장 경로: {os.path.abspath(file_path)}")
            except Exception as e:
                st.error(f"파일을 저장할 수 없습니다: {e}")
    except json.JSONDecodeError as e:
        st.error(f"JSON 구문 오류: {e}")

# ---------------------------------------------------------------------------
# Nextcloud 이미지 검색 기능
# ---------------------------------------------------------------------------

st.header("Nextcloud 이미지 검색")

# Nextcloud 서버 정보 입력
nc_url = st.text_input("Nextcloud 서버 URL")
nc_user = st.text_input("Nextcloud 사용자명")
nc_pass = st.text_input("Nextcloud 비밀번호", type="password")

# 검색할 JPG 파일명 입력
jpg_name = st.text_input("검색할 JPG 파일명")


def search_file(client: Client, dir_path: str, target: str):
    """Recursively search for target in Nextcloud directory"""
    try:
        items = client.list(dir_path, get_info=True)
    except Exception:
        return None
    for item in items:
        path = item.get('path')
        if item.get('isdir'):
            found = search_file(client, path, target)
            if found:
                return found
        else:
            if os.path.basename(path) == target:
                return path
    return None


if st.button("이미지 검색"):
    if not (nc_url and nc_user and nc_pass and jpg_name):
        st.warning("모든 입력 값을 채워주세요.")
    else:
        options = {
            'webdav_hostname': nc_url,
            'webdav_login': nc_user,
            'webdav_password': nc_pass,
        }
        try:
            client = Client(options)
            client.verify = True
            found_path = search_file(client, "/", jpg_name)
            if found_path:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    client.download_sync(remote_path=found_path, local_path=tmp.name)
                    st.image(tmp.name, caption=os.path.basename(found_path))
            else:
                st.warning("파일을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"Nextcloud 접근 실패: {e}")


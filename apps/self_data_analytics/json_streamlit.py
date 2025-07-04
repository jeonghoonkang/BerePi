import streamlit as st
import json
import os
import tempfile
from webdav3.client import Client
import traceback
import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth

from urllib.parse import unquote_plus
import urllib.parse


debug_prefix = "  "

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
WEBDAV_ENDPOINT = f"{nc_url}/remote.php/dav/files/{nc_user}/"
#remote.php/webdav
#url = f"{conf['nextcloud']['url']}/remote.php/dav/files/{conf['nextcloud']['username']}{conf['nextcloud']['remote_folder']}{current_path}"

HEADERS = {
    "Content-Type": "application/xml",
    "Depth": "infinity" # 하위 폴더까지 모두 검색
}


# --- WebDAV SEARCH 요청 XML 바디 ---
# 이 XML은 WebDAV SEARCH 요청의 핵심입니다.
# - D:filter: 검색 조건을 정의합니다.
# - D:prop: 응답으로 받을 파일의 속성(properties)을 정의합니다.
#   - D:displayname: 파일 이름
#   - D:getcontenttype: 파일 MIME 타입
#   - D:getlastmodified: 마지막 수정 시간
#   - D:getcontentlength: 파일 크기
#   - oc:fileid, oc:ownerid, oc:tags, oc:favorite 등 Nextcloud 고유 속성도 가능합니다.
#
# <D:contains xml:lang="en-US"> 은 특정 텍스트를 포함하는 파일을 찾습니다.
# <D:iscollection>true</D:iscollection> 는 폴더를, false는 파일을 의미합니다.
# Nextcloud WebDAV SEARCH는 파일 이름/속성 검색에 특화되어 있으며,
# 파일 내부 텍스트 검색(Full-text search)은 별도의 앱(FullTextSearch)을 설치해야 합니다.

def search_file(client: Client, dir_path: str, target: str, current_path=""):
    """Recursively search for a file named ``target`` and return its path."""

    search_dir = os.path.join(dir_path, current_path.lstrip("/")).rstrip("/")
    print(f"Searching for '{target}' in {search_dir}")

    tmp_url = nc_url + "/remote.php/dav/files/" + nc_user + search_dir
    print(f"WebDAV URL: {tmp_url}")

    response = requests.request(
        "PROPFIND",
        #WEBDAV_ENDPOINT + search_dir,
        tmp_url,
        auth=HTTPBasicAuth(nc_user, nc_pass),
        headers={"Depth": "1"},
        timeout=10,
    )

    if response.status_code != 207:
        print(f"Error accessing Nextcloud: {response.status_code}")
        return None

    from xml.etree import ElementTree
    tree = ElementTree.fromstring(response.content)

    for response_buff in tree.findall("{DAV:}response"):

        uhref = response_buff.find("{DAV:}href").text
        href = urllib.parse.unquote(uhref)
        relative_path = href.replace(
            f"/remote.php/dav/files/{nc_user}{search_dir}",
            "",
        ).lstrip("/")

        if not relative_path:  # skip current directory
            continue

        if href.endswith("/"):
            next_path = os.path.join(current_path, relative_path)
            found = search_file(client, dir_path, target, next_path)
            if found:
                return found
            continue

        filename = href.split("/")[-1]

        if filename == target:
            return os.path.join(search_dir, filename)

    return None


def search_files(client: Client, dir_path: str, target: str):
    """Search ``dir_path`` and all sub directories for ``target``.

    Parameters
    ----------
    client : Client
        Initialized WebDAV client.
    dir_path : str
        Directory path on the server to start searching from.
    target : str
        Filename to look for.

    Returns
    -------
    str or None
        Path of the first found file. ``None`` if not found.
    """

    return search_file(client, dir_path, target, "")


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
            st.success("Nextcloud에 성공적으로 연결되었습니다.")
            # 검색 실행
            if not jpg_name.endswith('.jpg'):
                jpg_name += '.jpg'
            st.write(f"'{jpg_name}' 파일을 검색 중...")

            #listtmp = client.list("/Photos/biz_card")  # 기본 폴더 확인, it is working, if client is connected by https://****:443/remote.php/webdav
            #st.write(f"기본 폴더 목록: {listtmp}")

            # 파일 검색
            found_path = search_files(client, "/Photos/biz_card", jpg_name)
            st.write(f"검색 결과: {found_path if found_path else '파일을 찾을 수 없습니다.'}")

            if found_path:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    local_tmp = tmp.name
                try:
                    found_path = found_path[1:]
                    print (f"Downloading file from Nextcloud: {found_path} to {local_tmp}")
                    client.download_sync(
                        remote_path=str(found_path),
                        local_path=str(local_tmp)
                    )
                    st.image(local_tmp, caption=os.path.basename(found_path))
                    st.write(f"다운로드 경로: {local_tmp}")
                except Exception as e:
                    error_details = traceback.format_exc()
                    st.error(
                        f"파일 다운로드 실패: 원격 경로 '{found_path}'\n{e}\n{error_details}"
                    )
                    print(f"Download error for '{found_path}': {e}\n{error_details}")
            else:
                st.warning("파일을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"Nextcloud 접근 실패: {e}")


import json
import streamlit as st
from nc_photo_list import list_photos


def main():
    st.title("Nextcloud Photo Metadata")
    url = st.text_input("Nextcloud URL")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    photo_dir = st.text_input("Photo directory", value="/Photos")

    if st.button("Fetch"):
        if not (url and username and password):
            st.warning("모든 정보를 입력하세요.")
        else:
            with st.spinner("이미지 정보를 가져오는 중..."):
                try:
                    photos = list_photos(url, username, password, photo_dir)
                    st.json(photos)
                except Exception as e:
                    st.error(str(e))


if __name__ == "__main__":
    main()

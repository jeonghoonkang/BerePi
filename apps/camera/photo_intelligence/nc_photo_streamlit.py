import json
import streamlit as st
import traceback

from nc_photo_list import list_photos


def main():
    st.title("Nextcloud Photo Metadata")
    url = st.text_input("Nextcloud URL")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    photo_dir = st.text_input("Photo directory", value="/Photos")
    method = st.selectbox("EXIF method", ["pillow", "exiftool"], index=0)
    measure_speed = st.checkbox("측정 모드 (두 방법 속도 비교)")

    if st.button("Fetch"):
        if not (url and username and password):
            st.warning("모든 정보를 입력하세요.")
        else:
            progress_text = st.empty()
            def cb(path):
                progress_text.write(f"Scanning {path}")

            with st.spinner("이미지 정보를 가져오는 중..."):
                try:
                    photos = list_photos(

                        url,
                        username,
                        password,
                        photo_dir,
                        progress_cb=cb,
                        exif_method=method,
                        measure_speed=measure_speed,
                    )
                    progress_text.write("완료")
                    st.json(photos)
                except Exception:
                    st.error(traceback.format_exc())


if __name__ == "__main__":
    main()

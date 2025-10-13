"""Streamlit interface to display the latest motion mosaic image."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import streamlit as st

from send_motion_mosaic_no_detect import (
    OUTPUT_MOSAIC,
    MOTION_DIR,
    KST,
    create_mosaic,
    latest_images,
)

STREAMLIT_MOSAIC = OUTPUT_MOSAIC.with_name("streamlit_motion_mosaic.jpg")


def _display_mosaic(image_path: Path, caption: str) -> None:
    """Render the mosaic image and associated caption in the UI."""

    st.image(str(image_path), caption=caption, use_column_width=True)
    st.caption(f"이미지 소스 디렉터리: {MOTION_DIR}")


def _select_recent_images(limit: int = 32) -> Iterable[Path]:
    """Return the most recent motion images up to ``limit`` entries."""

    return latest_images(limit)


def _build_caption(image_paths: Iterable[Path]) -> str:
    """Generate a caption for the mosaic using the newest image timestamp."""

    newest = max(image_paths, key=lambda p: p.stat().st_mtime)
    timestamp = datetime.fromtimestamp(newest.stat().st_mtime, KST)
    formatted = timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"최신 이미지: {formatted}"


st.set_page_config(page_title="BerePi Motion Mosaic", layout="wide")
st.title("Motion Mosaic 뷰어")
st.caption(
    "최근 모션 이미지를 모아 만든 모자이크를 확인하려면 아래 버튼을 눌러 주세요."
)

if "mosaic" not in st.session_state:
    st.session_state.mosaic = None

info_placeholder = st.empty()

if st.button("최근 사진 요청"):
    try:
        images = list(_select_recent_images())
    except Exception as exc:  # pragma: no cover - runtime feedback
        st.error(f"이미지 목록을 불러오는 중 오류가 발생했습니다: {exc}")
    else:
        if not images:
            st.warning(
                "모션 이미지가 없습니다. 카메라 또는 Motion 설정을 확인해 주세요."
            )
        else:
            with st.spinner("모자이크를 생성하고 있습니다..."):
                try:
                    mosaic_path = create_mosaic(images, STREAMLIT_MOSAIC, cols=8, rows=4)
                except Exception as exc:  # pragma: no cover - runtime feedback
                    st.error(f"모자이크 생성에 실패했습니다: {exc}")
                else:
                    caption = _build_caption(images)
                    st.session_state.mosaic = (mosaic_path, caption)
if st.session_state.mosaic is not None:
    mosaic_path, caption = st.session_state.mosaic
    st.success("모자이크를 불러왔습니다.")
    _display_mosaic(mosaic_path, caption)
else:
    info_placeholder.info("최근 사진을 확인하려면 '최근 사진 요청' 버튼을 눌러 주세요.")

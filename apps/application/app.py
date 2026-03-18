from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import streamlit as st
from PIL import Image, ImageDraw

try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:  # pragma: no cover - runtime dependency message
    st_canvas = None


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".gif", ".png"}
ACTION_CODES = {
    "지우기": "ERASE",
    "남기기": "KEEP",
    "자르기": "CROP",
}
CANVAS_MAX_WIDTH = 900
RESULT_IMAGE_WIDTH = 800
HISTORY_LIMIT = 1000
HISTORY_FILE = Path(__file__).resolve().parent / "scan_dir_history.txt"


def rerun() -> None:
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun()


def init_state() -> None:
    defaults = {
        "scan_dir": "",
        "image_files": [],
        "current_index": 0,
        "saved_box": None,
        "canvas_box": None,
        "last_scan_message": "",
        "batch_results": [],
        "last_processed_image": None,
        "scan_dir_history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def get_creation_time(path: Path) -> datetime:
    stat_result = path.stat()
    created = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    return datetime.fromtimestamp(created)


def scan_directory(directory: str) -> tuple[list[Path], str]:
    base_dir = Path(directory).expanduser()
    if not base_dir.exists():
        return [], "지정한 디렉토리가 존재하지 않습니다."
    if not base_dir.is_dir():
        return [], "지정한 경로가 디렉토리가 아닙니다."

    files = sorted(
        path
        for path in base_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        return [], "해당 디렉토리에 이미지 파일이 없습니다."
    return files, f"이미지 파일 {len(files)}개를 찾았습니다."


def load_scan_dir_history() -> list[str]:
    if not HISTORY_FILE.exists():
        return []

    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    history: list[str] = []
    seen: set[str] = set()
    for line in lines:
        value = line.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        history.append(value)
    return history[:HISTORY_LIMIT]


def save_scan_dir_history(directory: str) -> list[str]:
    normalized = str(Path(directory).expanduser())
    current_history = load_scan_dir_history()
    updated = [normalized]
    updated.extend(item for item in current_history if item != normalized)
    trimmed = updated[:HISTORY_LIMIT]
    HISTORY_FILE.write_text("\n".join(trimmed) + ("\n" if trimmed else ""), encoding="utf-8")
    return trimmed


def get_image_info(path: Path) -> dict[str, str | int]:
    with Image.open(path) as image:
        width, height = image.size
    size_bytes = path.stat().st_size
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": size_bytes,
        "size_text": format_size(size_bytes),
        "dimensions": f"{width} x {height}",
        "width": width,
        "height": height,
        "created_at": get_creation_time(path).strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_preview_image(image: Image.Image, box: tuple[int, int, int, int] | None) -> Image.Image:
    preview = image.convert("RGBA").copy()
    if box:
        drawer = ImageDraw.Draw(preview)
        drawer.rectangle(box, outline=(255, 0, 0, 255), width=3)
    return preview


def save_processed_image(
    image_path: Path,
    action_name: str,
    box: tuple[int, int, int, int],
) -> Path:
    action_code = ACTION_CODES[action_name]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with Image.open(image_path) as original:
        image = original.convert("RGBA")
        left, top, right, bottom = box
        left = max(0, min(left, image.width - 1))
        top = max(0, min(top, image.height - 1))
        right = max(left + 1, min(right, image.width))
        bottom = max(top + 1, min(bottom, image.height))

        if action_name == "지우기":
            result = image.copy()
            drawer = ImageDraw.Draw(result)
            drawer.rectangle((left, top, right, bottom), fill=(255, 255, 255, 255))
        elif action_name == "남기기":
            result = Image.new("RGBA", image.size, (255, 255, 255, 255))
            selected = image.crop((left, top, right, bottom))
            result.paste(selected, (left, top))
        elif action_name == "자르기":
            result = image.crop((left, top, right, bottom))
        else:  # pragma: no cover - guarded by UI selectbox
            raise ValueError(f"Unsupported action: {action_name}")

        if result.mode in {"RGBA", "LA"} and image_path.suffix.lower() in {".jpg", ".jpeg"}:
            result = result.convert("RGB")

        output_path = image_path.with_name(
            f"{image_path.stem}_{timestamp}_{action_code}{image_path.suffix.lower()}"
        )
        result.save(output_path)
        return output_path


def get_selected_box(canvas_data: dict, image_size: tuple[int, int], canvas_width: int) -> tuple[int, int, int, int] | None:
    objects = canvas_data.get("objects") or []
    if not objects:
        return None

    rect = objects[-1]
    scale = image_size[0] / canvas_width
    left = max(0, int(rect["left"] * scale))
    top = max(0, int(rect["top"] * scale))
    width = max(1, int(rect["width"] * rect.get("scaleX", 1) * scale))
    height = max(1, int(rect["height"] * rect.get("scaleY", 1) * scale))
    right = min(image_size[0], left + width)
    bottom = min(image_size[1], top + height)

    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def summarize_files(paths: Iterable[Path]) -> tuple[int, int]:
    total_files = 0
    total_bytes = 0
    for path in paths:
        total_files += 1
        total_bytes += path.stat().st_size
    return total_files, total_bytes


def move_to_next_image() -> None:
    image_files = st.session_state.image_files
    if not image_files:
        st.session_state.current_index = 0
        return
    st.session_state.current_index = min(st.session_state.current_index + 1, len(image_files) - 1)


def main() -> None:
    st.set_page_config(page_title="이미지 전처리", layout="wide")
    init_state()
    if not st.session_state.scan_dir_history:
        st.session_state.scan_dir_history = load_scan_dir_history()
        if not st.session_state.scan_dir and st.session_state.scan_dir_history:
            st.session_state.scan_dir = st.session_state.scan_dir_history[0]

    st.title("이미지 전처리 애플리케이션")
    st.caption("디렉토리를 스캔하고, 좌표 박스를 지정한 뒤 이미지 전처리를 실행합니다.")

    history_options = [""] + st.session_state.scan_dir_history
    selected_history = st.selectbox(
        "스캔 디렉토리 히스토리",
        options=history_options,
        index=history_options.index(st.session_state.scan_dir) if st.session_state.scan_dir in history_options else 0,
    )
    if selected_history and selected_history != st.session_state.scan_dir:
        st.session_state.scan_dir = selected_history

    path_col, button_col = st.columns([5, 1])
    with path_col:
        scan_dir = st.text_input(
            "스캔할 디렉토리",
            value=st.session_state.scan_dir,
            placeholder="/path/to/images",
        )
    with button_col:
        scan_clicked = st.button("Scan", use_container_width=True)

    if scan_clicked:
        st.session_state.scan_dir = scan_dir
        files, message = scan_directory(scan_dir)
        if scan_dir.strip():
            st.session_state.scan_dir_history = save_scan_dir_history(scan_dir)
        st.session_state.image_files = files
        st.session_state.current_index = 0
        st.session_state.saved_box = None
        st.session_state.canvas_box = None
        st.session_state.batch_results = []
        st.session_state.last_processed_image = None
        st.session_state.last_scan_message = message

    if st.session_state.last_scan_message:
        if st.session_state.image_files:
            st.success(st.session_state.last_scan_message)
        else:
            st.warning(st.session_state.last_scan_message)

    if not st.session_state.image_files:
        st.info("파일이 없다고 표시하는 창입니다. 지정한 디렉토리를 스캔해 주세요.")
        return

    total_files, total_bytes = summarize_files(st.session_state.image_files)
    metric_cols = st.columns(2)
    metric_cols[0].metric("파일 개수", f"{total_files}개")
    metric_cols[1].metric("총 용량", format_size(total_bytes))

    file_options = [str(path) for path in st.session_state.image_files]
    selected_path_str = st.selectbox(
        "현재 작업 파일",
        options=file_options,
        index=st.session_state.current_index,
    )
    st.session_state.current_index = file_options.index(selected_path_str)
    current_path = st.session_state.image_files[st.session_state.current_index]
    current_info = get_image_info(current_path)

    st.subheader("현재 화면 이미지 정보")
    info_cols = st.columns(5)
    info_cols[0].text_input("경로", value=current_info["path"], disabled=True)
    info_cols[1].text_input("이름", value=current_info["name"], disabled=True)
    info_cols[2].text_input("용량", value=current_info["size_text"], disabled=True)
    info_cols[3].text_input("사이즈", value=current_info["dimensions"], disabled=True)
    info_cols[4].text_input("생성 시간", value=current_info["created_at"], disabled=True)

    action_name = st.selectbox("전처리 동작", options=list(ACTION_CODES.keys()))

    with Image.open(current_path) as current_image:
        working_image = current_image.convert("RGBA")
        original_width, original_height = working_image.size
        canvas_width = min(original_width, CANVAS_MAX_WIDTH)
        canvas_height = max(1, int(original_height * (canvas_width / original_width)))
        preview_image = build_preview_image(working_image, st.session_state.saved_box)

        st.subheader("박스 선택")
        if st_canvas is None:
            st.error(
                "`streamlit-drawable-canvas` 패키지가 필요합니다. "
                "`pip install -r apps/application/requirements.txt` 후 실행해 주세요."
            )
            st.image(preview_image, caption="미리보기", use_container_width=True)
            return

        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.12)",
            stroke_width=2,
            stroke_color="#ff0000",
            background_image=preview_image,
            update_streamlit=True,
            height=canvas_height,
            width=canvas_width,
            drawing_mode="rect",
            key=f"canvas_{current_path}",
        )

    canvas_data = canvas_result.json_data if canvas_result else {}
    selected_box = get_selected_box(canvas_data or {}, (original_width, original_height), canvas_width)
    st.session_state.canvas_box = selected_box

    status_cols = st.columns([1, 1, 3])
    if status_cols[0].button("상태 저장", use_container_width=True):
        if st.session_state.canvas_box is None:
            st.warning("먼저 마우스로 박스를 그려 주세요.")
        else:
            st.session_state.saved_box = st.session_state.canvas_box
            st.success(f"좌표 저장 완료: {st.session_state.saved_box}")

    if status_cols[1].button("저장 좌표 초기화", use_container_width=True):
        st.session_state.saved_box = None
        st.session_state.canvas_box = None
        st.info("저장된 좌표를 초기화했습니다.")

    saved_box = st.session_state.saved_box
    status_cols[2].text_input(
        "현재 저장 좌표",
        value=str(saved_box) if saved_box else "저장된 좌표 없음",
        disabled=True,
    )

    st.subheader("전처리 실행")
    if st.button("현재 파일 전처리 저장", use_container_width=True):
        if saved_box is None:
            st.warning("전처리 전에 좌표를 저장해 주세요.")
        else:
            output_path = save_processed_image(current_path, action_name, saved_box)
            st.success(f"전처리 결과 저장: {output_path}")

    exec_cols = st.columns(2)
    if exec_cols[0].button("디렉토리 전체 일괄 처리", use_container_width=True):
        if saved_box is None:
            st.warning("일괄 처리 전에 좌표를 저장해 주세요.")
        else:
            results = []
            for image_path in st.session_state.image_files:
                output_path = save_processed_image(image_path, action_name, saved_box)
                results.append(output_path)
            st.session_state.batch_results = results
            st.success(f"{len(results)}개 파일을 일괄 처리했습니다.")

    if exec_cols[1].button("한개씩 전처리", use_container_width=True):
        if saved_box is None:
            st.warning("전처리 전에 좌표를 저장해 주세요.")
        else:
            output_path = save_processed_image(current_path, action_name, saved_box)
            st.session_state.last_processed_image = str(output_path)
            st.success(f"현재 파일 처리 완료: {output_path}")
            move_to_next_image()
            rerun()

    if st.session_state.batch_results:
        st.subheader("최근 일괄 처리 결과")
        for result in st.session_state.batch_results[:20]:
            st.write(str(result))
        if len(st.session_state.batch_results) > 20:
            st.caption(f"총 {len(st.session_state.batch_results)}개 중 20개만 표시했습니다.")

    if st.session_state.last_processed_image:
        st.subheader("한개씩 처리 결과")
        st.text_input(
            "결과 파일",
            value=st.session_state.last_processed_image,
            disabled=True,
        )
        st.image(st.session_state.last_processed_image, caption="처리된 결과 이미지", width=RESULT_IMAGE_WIDTH)


if __name__ == "__main__":
    main()

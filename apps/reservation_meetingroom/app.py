from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import qrcode
import socket
import streamlit as st
from streamlit_calendar import calendar

import db


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "meetingroom.sqlite3"


def _iso(dt_: datetime) -> str:
    if dt_.tzinfo is None:
        dt_ = dt_.replace(tzinfo=timezone.utc)
    return dt_.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _event_color(room_id: int) -> str:
    palette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    return palette[(room_id - 1) % len(palette)]


def _build_events(rooms_by_id: dict[int, db.Room], reservations: list[db.Reservation]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for r in reservations:
        room_name = rooms_by_id.get(r.room_id, db.Room(r.room_id, f"Room {r.room_id}")).name
        events.append(
            {
                "id": str(r.id),
                "title": f"[{room_name}] {r.title}".strip(),
                "start": r.start_iso,
                "end": r.end_iso,
                "backgroundColor": _event_color(r.room_id),
                "borderColor": _event_color(r.room_id),
            }
        )
    return events


def _reservation_qr_payload(
    *,
    base_url: str,
    reservation: db.Reservation,
    room_name: str,
) -> str:
    start = reservation.start_iso
    end = reservation.end_iso
    text = (
        "미팅룸 예약\n"
        f"- 회의실: {room_name}\n"
        f"- 제목: {reservation.title}\n"
        f"- 시작: {start}\n"
        f"- 종료: {end}\n"
        f"- 예약ID: {reservation.id}\n"
    )
    base_url = base_url.strip()
    if base_url:
        joiner = "&" if "?" in base_url else "?"
        return f"{base_url}{joiner}event_id={reservation.id}"
    return text


def _qr_image(payload: str):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # qrcode는 PilImage 래퍼를 반환할 수 있어 streamlit 호환 형태로 변환
    if hasattr(img, "get_image"):
        img = img.get_image()
    return img


def _ensure_default_rooms() -> None:
    rooms = db.list_rooms(DB_PATH)
    if rooms:
        return
    defaults = [f"회의실{i}" for i in range(1, 6)]
    db.upsert_rooms(DB_PATH, defaults, max_rooms=10)


def _ui_room_settings() -> None:
    st.sidebar.subheader("회의실 설정 (최대 10개)")
    rooms = db.list_rooms(DB_PATH)
    raw = "\n".join([r.name for r in rooms]) if rooms else ""
    names_text = st.sidebar.text_area("회의실 이름 (줄바꿈으로 구분)", value=raw, height=220)
    if st.sidebar.button("회의실 목록 저장", use_container_width=True):
        names = [line.strip() for line in names_text.splitlines()]
        db.upsert_rooms(DB_PATH, names, max_rooms=10)
        st.sidebar.success("저장했습니다.")


def _ui_base_url() -> str:
    st.sidebar.subheader("모바일 접속/QR")
    value = st.sidebar.text_input(
        "Base URL (선택)",
        value=st.session_state.get("base_url", ""),
        placeholder="예: http://192.168.0.10:8501",
        help="입력하면 QR에 URL(event_id 포함)이 들어갑니다. 비워두면 예약 요약 텍스트 QR을 만듭니다.",
    ).strip()

    try:
        port = int(st.get_option("server.port") or 8501)
    except Exception:
        port = 8501

    st.sidebar.caption("현재 시스템 접속 주소(참고)")
    ips = _detect_local_ips()
    if ips:
        lines = [f"http://{ip}:{port}" for ip in ips]
        st.sidebar.code("\n".join(lines))
    else:
        st.sidebar.code(f"http://<PC_IP>:{port}")
    return value


def _detect_local_ips() -> list[str]:
    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
        finally:
            s.close()
    except Exception:
        pass

    all_ips = sorted(ips)
    preferred = [ip for ip in all_ips if ip.startswith("10.") or ip.startswith("192.")]
    if preferred:
        return preferred
    return all_ips


def _pick_room(rooms: list[db.Room], label: str, default_room_id: Optional[int] = None) -> int:
    if not rooms:
        st.warning("회의실이 없습니다. 왼쪽 사이드바에서 회의실 이름을 먼저 등록하세요.")
        return -1
    idx = 0
    if default_room_id is not None:
        for i, r in enumerate(rooms):
            if r.id == default_room_id:
                idx = i
                break
    chosen = st.selectbox(label, rooms, index=idx, format_func=lambda r: r.name)
    return int(chosen.id)


def _dt_inputs(prefix: str, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    c1, c2 = st.columns(2)
    with c1:
        start_d = st.date_input(f"{prefix} 시작 날짜", value=start.date(), key=f"{prefix}_sd")
        start_t = st.time_input(f"{prefix} 시작 시간", value=start.time().replace(second=0, microsecond=0), key=f"{prefix}_st")
    with c2:
        end_d = st.date_input(f"{prefix} 종료 날짜", value=end.date(), key=f"{prefix}_ed")
        end_t = st.time_input(f"{prefix} 종료 시간", value=end.time().replace(second=0, microsecond=0), key=f"{prefix}_et")
    start_dt = datetime.combine(start_d, start_t).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_d, end_t).replace(tzinfo=timezone.utc)
    return start_dt, end_dt


def _normalize_range(start_dt: datetime, end_dt: datetime) -> tuple[datetime, datetime]:
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)
    return start_dt, end_dt


def _handle_calendar_actions(cal_state: dict[str, Any]) -> None:
    # streamlit-calendar 반환 값은 버전/설정에 따라 키가 조금씩 다를 수 있어 방어적으로 처리합니다.
    if not isinstance(cal_state, dict):
        return

    if "select" in cal_state and isinstance(cal_state["select"], dict):
        sel = cal_state["select"]
        start = sel.get("start")
        end = sel.get("end")
        if isinstance(start, str) and isinstance(end, str):
            st.session_state["draft_start_iso"] = start
            st.session_state["draft_end_iso"] = end
            st.session_state["selected_event_id"] = None

    if "eventClick" in cal_state and isinstance(cal_state["eventClick"], dict):
        ev = cal_state["eventClick"].get("event", {})
        ev_id = ev.get("id")
        if ev_id is not None:
            try:
                st.session_state["selected_event_id"] = int(ev_id)
            except ValueError:
                st.session_state["selected_event_id"] = None

    if "eventChange" in cal_state and isinstance(cal_state["eventChange"], dict):
        ev = cal_state["eventChange"].get("event", {})
        ev_id = ev.get("id")
        start = ev.get("start")
        end = ev.get("end")
        if isinstance(ev_id, str) and isinstance(start, str) and isinstance(end, str):
            try:
                rid = int(ev_id)
            except ValueError:
                return
            res = db.get_reservation(DB_PATH, rid)
            if res is None:
                return
            # 제목/회의실은 그대로 두고 시간만 업데이트
            if db.has_conflict(DB_PATH, res.room_id, start, end, exclude_reservation_id=rid):
                st.warning("해당 시간대에 이미 예약이 있어 시간 변경을 반영하지 않았습니다.")
                return
            db.update_reservation(DB_PATH, rid, res.room_id, res.title, start, end)
            st.toast("시간 변경을 저장했습니다.")


def main() -> None:
    st.set_page_config(page_title="미팅룸 예약", layout="wide")
    st.title("미팅룸 예약 (캘린더 + QR)")

    db.init_db(DB_PATH)
    _ensure_default_rooms()

    _ui_room_settings()
    base_url = _ui_base_url()
    st.session_state["base_url"] = base_url

    rooms = db.list_rooms(DB_PATH)
    rooms_by_id = {r.id: r for r in rooms}

    st.sidebar.subheader("표시 필터")
    filter_choice = st.sidebar.selectbox(
        "캘린더 표시",
        options=["전체", "회의실별"],
        index=0,
    )
    room_filter_id: Optional[int] = None
    if filter_choice == "회의실별":
        rid = _pick_room(rooms, "표시할 회의실", None)
        room_filter_id = rid if rid > 0 else None

    reservations = db.list_reservations(DB_PATH, room_filter_id)
    events = _build_events(rooms_by_id, reservations)

    default_date = date.today().isoformat()
    options = {
        "initialView": "timeGridWeek",
        "initialDate": default_date,
        "selectable": True,
        "editable": True,
        "slotMinTime": "06:00:00",
        "slotMaxTime": "23:00:00",
        "nowIndicator": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
    }

    cal_state = calendar(events=events, options=options, custom_css=None, key="calendar")
    _handle_calendar_actions(cal_state)

    st.divider()

    qs_event_id = st.query_params.get("event_id")
    if qs_event_id and st.session_state.get("selected_event_id") is None:
        try:
            st.session_state["selected_event_id"] = int(qs_event_id)
        except ValueError:
            pass

    selected_id = st.session_state.get("selected_event_id")
    draft_start_iso = st.session_state.get("draft_start_iso")
    draft_end_iso = st.session_state.get("draft_end_iso")

    c_left, c_right = st.columns([1.2, 0.8])
    with c_left:
        st.subheader("예약 생성/수정")

        if selected_id:
            res = db.get_reservation(DB_PATH, int(selected_id))
        else:
            res = None

        if res is not None:
            mode = "edit"
            start_dt = _parse_iso(res.start_iso)
            end_dt = _parse_iso(res.end_iso)
            default_room_id = res.room_id
            default_title = res.title
        else:
            mode = "create"
            if isinstance(draft_start_iso, str) and isinstance(draft_end_iso, str):
                start_dt = _parse_iso(draft_start_iso)
                end_dt = _parse_iso(draft_end_iso)
            else:
                now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
                start_dt = now
                end_dt = now + timedelta(hours=1)
            default_room_id = rooms[0].id if rooms else None
            default_title = ""

        room_id = _pick_room(rooms, "회의실", default_room_id)
        title = st.text_input("제목", value=default_title, placeholder="예: 주간 회의")

        start_dt, end_dt = _dt_inputs("예약", start_dt, end_dt)
        start_dt, end_dt = _normalize_range(start_dt, end_dt)

        if room_id > 0:
            conflict = db.has_conflict(
                DB_PATH,
                room_id,
                _iso(start_dt),
                _iso(end_dt),
                exclude_reservation_id=(res.id if res else None),
            )
            if conflict:
                st.error("같은 회의실에 겹치는 예약이 있습니다. 시간을 조정해 주세요.")

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("저장", use_container_width=True, disabled=(room_id <= 0)):
                if not title.strip():
                    st.error("제목을 입력해 주세요.")
                else:
                    if db.has_conflict(
                        DB_PATH,
                        room_id,
                        _iso(start_dt),
                        _iso(end_dt),
                        exclude_reservation_id=(res.id if res else None),
                    ):
                        st.error("겹치는 예약이 있어 저장할 수 없습니다.")
                    else:
                        if mode == "create":
                            new_id = db.create_reservation(DB_PATH, room_id, title.strip(), _iso(start_dt), _iso(end_dt))
                            st.session_state["selected_event_id"] = new_id
                            st.success(f"예약을 생성했습니다. (ID={new_id})")
                        else:
                            db.update_reservation(DB_PATH, res.id, room_id, title.strip(), _iso(start_dt), _iso(end_dt))
                            st.success(f"예약을 수정했습니다. (ID={res.id})")
                        st.rerun()

        with b2:
            if st.button("새 예약", use_container_width=True):
                st.session_state["selected_event_id"] = None
                st.session_state["draft_start_iso"] = None
                st.session_state["draft_end_iso"] = None
                st.rerun()

        with b3:
            if st.button("삭제", use_container_width=True, disabled=(res is None)):
                if res is not None:
                    db.delete_reservation(DB_PATH, res.id)
                    st.session_state["selected_event_id"] = None
                    st.success("삭제했습니다.")
                    st.rerun()

    with c_right:
        st.subheader("QR 코드")
        if selected_id:
            res = db.get_reservation(DB_PATH, int(selected_id))
        else:
            res = None

        if res is None:
            st.info("캘린더에서 예약을 클릭하거나, 예약을 저장하면 QR을 표시합니다.")
        else:
            room_name = rooms_by_id.get(res.room_id, db.Room(res.room_id, f"Room {res.room_id}")).name
            payload = _reservation_qr_payload(base_url=base_url, reservation=res, room_name=room_name)
            img = _qr_image(payload)
            st.image(img, caption="휴대폰으로 스캔", use_container_width=True)
            with st.expander("QR 내용 보기"):
                st.code(payload)


if __name__ == "__main__":
    main()


from __future__ import annotations

import html
import ipaddress
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "servers.json"

DEFAULT_HEX_COUNT = 24
MAX_HEX_COUNT = 200
HEX_RADIUS = 52
HEX_GAP = 10
MAP_MAX_WIDTH = 980
MAP_MAX_HEIGHT = 640
MAP_MIN_RADIUS = 20


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def row_label(row_index: int) -> str:
    label = ""
    value = row_index
    while True:
        label = chr(65 + value % 26) + label
        value = value // 26 - 1
        if value < 0:
            return label


def auto_columns(hex_count: int) -> int:
    return max(1, math.ceil(math.sqrt(hex_count)))


def grid_rows(hex_count: int, columns: int) -> int:
    return max(1, math.ceil(hex_count / columns))


def zone_ids_for(hex_count: int, columns: int) -> list[str]:
    zones: list[str] = []
    for index in range(hex_count):
        row = index // columns
        col = index % columns
        zones.append(f"{row_label(row)}{col + 1}")
    return zones


def current_zone_ids(data: dict) -> list[str]:
    grid = data["grid"]
    return zone_ids_for(int(grid["hex_count"]), int(grid["columns"]))


def create_zone(zone_id: str) -> dict:
    return {
        "name": f"Zone {zone_id}",
        "description": "",
        "servers": [],
    }


def create_data(hex_count: int, columns: Optional[int] = None) -> dict:
    hex_count = max(1, min(int(hex_count), MAX_HEX_COUNT))
    columns = int(columns or auto_columns(hex_count))
    columns = max(1, min(columns, hex_count))
    zones = {zone_id: create_zone(zone_id) for zone_id in zone_ids_for(hex_count, columns)}
    return {
        "version": 2,
        "updated_at": now_text(),
        "grid": {
            "hex_count": hex_count,
            "columns": columns,
        },
        "zones": zones,
    }


def parse_zone_position(zone_id: str) -> tuple[str, int]:
    letters = "".join(ch for ch in zone_id if ch.isalpha())
    digits = "".join(ch for ch in zone_id if ch.isdigit())
    return letters or "A", int(digits or "1")


def normalize_data(data: dict) -> dict:
    data.setdefault("version", 2)
    data.setdefault("updated_at", now_text())
    data.setdefault("zones", {})

    if "grid" not in data:
        zone_keys = list(data["zones"].keys())
        hex_count = len(zone_keys) or DEFAULT_HEX_COUNT
        columns = max((parse_zone_position(zone_id)[1] for zone_id in zone_keys), default=auto_columns(hex_count))
        data["grid"] = {"hex_count": hex_count, "columns": columns}

    hex_count = max(1, min(int(data["grid"].get("hex_count", DEFAULT_HEX_COUNT)), MAX_HEX_COUNT))
    columns = int(data["grid"].get("columns") or auto_columns(hex_count))
    columns = max(1, min(columns, hex_count))
    data["grid"] = {"hex_count": hex_count, "columns": columns}

    for zone_id in current_zone_ids(data):
        data["zones"].setdefault(zone_id, create_zone(zone_id))
        data["zones"][zone_id].setdefault("name", f"Zone {zone_id}")
        data["zones"][zone_id].setdefault("description", "")
        data["zones"][zone_id].setdefault("servers", [])
        for server in data["zones"][zone_id]["servers"]:
            server.setdefault("id", uuid4().hex)
            server.setdefault("status", "active")
            server.setdefault("memo", "")
            server.setdefault("created_at", now_text())
            server.setdefault("updated_at", now_text())

    return data


def load_data() -> Optional[dict]:
    if not DATA_FILE.exists():
        return None

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return normalize_data(json.load(file))


def save_data(data: dict) -> None:
    data["updated_at"] = now_text()
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_query_zone(data: dict) -> str:
    valid_zones = current_zone_ids(data)
    try:
        value = st.query_params.get("zone", valid_zones[0])
    except AttributeError:
        value = st.experimental_get_query_params().get("zone", [valid_zones[0]])[0]

    if isinstance(value, list):
        value = value[0] if value else valid_zones[0]
    return value if value in valid_zones else valid_zones[0]


def set_query_zone(zone_id: str) -> None:
    try:
        st.query_params["zone"] = zone_id
    except AttributeError:
        st.experimental_set_query_params(zone=zone_id)


def validate_server(name: str, private_ip: str, public_ip: str, port: int) -> list[str]:
    errors: list[str] = []
    if not name.strip():
        errors.append("서버명을 입력해 주세요.")
    for label, value in [("IP주소", private_ip), ("Public IP", public_ip)]:
        if value.strip():
            try:
                ipaddress.ip_address(value.strip())
            except ValueError:
                errors.append(f"{label} 형식이 올바르지 않습니다: {value}")
    if not (1 <= int(port) <= 65535):
        errors.append("포트번호는 1부터 65535 사이여야 합니다.")
    return errors


def server_rows(servers: list[dict]) -> list[dict]:
    return [
        {
            "서버명": server.get("name", ""),
            "IP주소": server.get("private_ip", ""),
            "Public IP": server.get("public_ip", ""),
            "포트": server.get("port", ""),
            "상태": server.get("status", "unknown"),
            "메모": server.get("memo", ""),
        }
        for server in servers
    ]


def all_server_count(data: dict) -> int:
    return sum(len(zone.get("servers", [])) for zone in data["zones"].values())


def move_removed_zone_servers(data: dict, next_zone_ids: list[str]) -> None:
    if not next_zone_ids:
        return
    fallback_zone = next_zone_ids[-1]
    active = set(next_zone_ids)
    for zone_id, zone in list(data["zones"].items()):
        if zone_id in active:
            continue
        servers = zone.get("servers", [])
        if servers:
            data["zones"].setdefault(fallback_zone, create_zone(fallback_zone))
            data["zones"][fallback_zone].setdefault("servers", []).extend(servers)
        del data["zones"][zone_id]


def resize_grid(data: dict, hex_count: int, columns: int) -> dict:
    hex_count = max(1, min(int(hex_count), MAX_HEX_COUNT))
    columns = max(1, min(int(columns), hex_count))
    next_zone_ids = zone_ids_for(hex_count, columns)

    data["grid"] = {"hex_count": hex_count, "columns": columns}
    for zone_id in next_zone_ids:
        data["zones"].setdefault(zone_id, create_zone(zone_id))
    move_removed_zone_servers(data, next_zone_ids)
    return normalize_data(data)


def fit_hex_radius(hex_count: int, columns: int) -> int:
    rows = grid_rows(hex_count, columns)
    width_units = 1.75 * max(columns - 1, 0) + 3 + (0.875 if rows > 1 else 0)
    height_units = 1.52 * max(rows - 1, 0) + 2.8
    gap_width = HEX_GAP * max(columns - 1, 0) + 36
    gap_height = HEX_GAP * max(rows - 1, 0) + 36
    radius_by_width = (MAP_MAX_WIDTH - gap_width) / max(width_units, 1)
    radius_by_height = (MAP_MAX_HEIGHT - gap_height) / max(height_units, 1)
    return int(max(MAP_MIN_RADIUS, min(HEX_RADIUS, radius_by_width, radius_by_height)))


def hex_points(cx: float, cy: float, radius: float) -> str:
    points = []
    for index in range(6):
        angle = 60 * index - 30
        radians = math.radians(angle)
        x = cx + radius * math.cos(radians)
        y = cy + radius * math.sin(radians)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def build_hex_map(data: dict, selected_zone: str) -> tuple[str, int]:
    zones = data["zones"]
    grid = data["grid"]
    columns = int(grid["columns"])
    hex_count = int(grid["hex_count"])
    rows = grid_rows(hex_count, columns)
    radius = fit_hex_radius(hex_count, columns)
    step_x = radius * 1.75 + HEX_GAP
    step_y = radius * 1.52 + HEX_GAP
    margin = radius + 18
    width = int(margin * 2 + step_x * (columns - 1) + radius + (step_x / 2 if rows > 1 else 0))
    height = int(margin * 2 + step_y * (rows - 1) + radius * 0.8)

    hexes: list[str] = []
    for index, zone_id in enumerate(current_zone_ids(data)):
        row = index // columns
        col = index % columns
        cx = margin + col * step_x + (step_x / 2 if row % 2 else 0)
        cy = margin + row * step_y
        server_count = len(zones[zone_id]["servers"])
        zone_name = zones[zone_id].get("name", f"Zone {zone_id}")
        selected_class = " selected" if zone_id == selected_zone else ""
        href = f"?zone={html.escape(zone_id)}"
        title = html.escape(f"{zone_name} / {server_count} servers")
        label = html.escape(zone_id)
        count = html.escape(str(server_count))
        points = hex_points(cx, cy, radius)
        hexes.append(
            f"""
            <a href="{href}" target="_parent" class="hex-link" aria-label="{title}">
              <polygon class="hex-cell{selected_class}" points="{points}">
                <title>{title}</title>
              </polygon>
              <text class="hex-label" x="{cx:.1f}" y="{cy - 4:.1f}">{label}</text>
              <text class="hex-count" x="{cx:.1f}" y="{cy + 18:.1f}">{count}</text>
            </a>
            """
        )

    map_html = f"""
    <style>
      .server-map-wrap {{
        width: 100%;
        overflow: hidden;
        padding: 6px 0 12px;
        font-family: Arial, sans-serif;
      }}
      .server-map {{
        display: block;
        width: 100%;
        height: auto;
        max-height: {MAP_MAX_HEIGHT}px;
        background: #f7f9fb;
        border: 1px solid #d8e0ea;
        border-radius: 8px;
      }}
      .hex-cell {{
        fill: #e7eef6;
        stroke: #7b8da1;
        stroke-width: 2;
        transition: fill 120ms ease, stroke 120ms ease, transform 120ms ease;
        transform-box: fill-box;
        transform-origin: center;
      }}
      .hex-link:hover .hex-cell {{
        fill: #d6e8f8;
        stroke: #2f73b8;
        transform: scale(1.035);
      }}
      .hex-cell.selected {{
        fill: #2f73b8;
        stroke: #153d66;
      }}
      .hex-label {{
        fill: #16202a;
        font: 700 18px sans-serif;
        pointer-events: none;
        text-anchor: middle;
      }}
      .hex-count {{
        fill: #445568;
        font: 600 14px sans-serif;
        pointer-events: none;
        text-anchor: middle;
      }}
      .selected ~ .hex-label,
      .selected ~ .hex-count {{
        fill: #ffffff;
      }}
    </style>
    <div class="server-map-wrap">
      <svg class="server-map" viewBox="0 0 {width} {height}" role="img">
        <title>Hexagon server zone map</title>
        {''.join(hexes)}
      </svg>
    </div>
    """
    return map_html, min(max(height + 28, 260), MAP_MAX_HEIGHT + 42)


def render_initial_setup() -> None:
    st.title("tinyGW Server List")
    st.caption("처음 실행 설정입니다. 사용할 hexagon 조각 개수를 등록해 주세요.")

    with st.form("initial_setup"):
        hex_count = st.number_input(
            "Hexagon 개수",
            min_value=1,
            max_value=MAX_HEX_COUNT,
            value=DEFAULT_HEX_COUNT,
            step=1,
        )
        default_columns = auto_columns(int(hex_count))
        columns = st.number_input(
            "한 줄당 hexagon 개수",
            min_value=1,
            max_value=int(hex_count),
            value=default_columns,
            step=1,
        )
        submitted = st.form_submit_button("서버 리스트 시작", use_container_width=True)

    if submitted:
        data = create_data(int(hex_count), int(columns))
        save_data(data)
        set_query_zone(current_zone_ids(data)[0])
        st.success("Hexagon 구성을 저장했습니다.")
        st.rerun()


def render_grid_settings(data: dict) -> None:
    grid = data["grid"]
    st.subheader("Hexagon 구성")
    st.caption("개수를 줄이면 사라지는 조각의 서버는 마지막 조각으로 이동합니다.")

    action_col1, action_col2, action_col3 = st.columns([1, 1, 2])
    with action_col1:
        if st.button("Hexagon 1개 추가", use_container_width=True, disabled=int(grid["hex_count"]) >= MAX_HEX_COUNT):
            next_count = int(grid["hex_count"]) + 1
            resize_grid(data, next_count, min(int(grid["columns"]), next_count))
            save_data(data)
            set_query_zone(current_zone_ids(data)[-1])
            st.success("Hexagon을 추가했습니다.")
            st.rerun()
    with action_col2:
        if st.button("마지막 Hexagon 삭제", use_container_width=True, disabled=int(grid["hex_count"]) <= 1):
            next_count = int(grid["hex_count"]) - 1
            resize_grid(data, next_count, min(int(grid["columns"]), next_count))
            save_data(data)
            set_query_zone(current_zone_ids(data)[-1])
            st.success("마지막 Hexagon을 삭제했습니다.")
            st.rerun()
    with action_col3:
        st.caption(f"현재 한 줄당 {int(grid['columns'])}개, 최대 {MAX_HEX_COUNT}개까지 관리할 수 있습니다.")

    with st.form("grid_settings"):
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            hex_count = st.number_input(
                "Hexagon 개수",
                min_value=1,
                max_value=MAX_HEX_COUNT,
                value=int(grid["hex_count"]),
                step=1,
            )
        with col2:
            columns = st.number_input(
                "한 줄당 hexagon 개수",
                min_value=1,
                max_value=int(hex_count),
                value=min(int(grid["columns"]), int(hex_count)),
                step=1,
            )
        with col3:
            st.write("")
            st.write("")
            submitted = st.form_submit_button("구성 저장", use_container_width=True)

        if submitted:
            resize_grid(data, int(hex_count), int(columns))
            save_data(data)
            first_zone = current_zone_ids(data)[0]
            set_query_zone(first_zone)
            st.success("Hexagon 구성을 저장했습니다.")
            st.rerun()


def render_zone_settings(data: dict, zone_id: str) -> None:
    zone = data["zones"][zone_id]
    with st.form("zone_settings"):
        st.subheader("선택 Hexagon 편집")
        col1, col2 = st.columns([1, 2])
        with col1:
            zone_name = st.text_input("조각 이름", value=zone.get("name", f"Zone {zone_id}"))
        with col2:
            description = st.text_area("설명", value=zone.get("description", ""), height=72)
        if st.form_submit_button("조각 정보 저장", use_container_width=True):
            zone["name"] = zone_name.strip() or f"Zone {zone_id}"
            zone["description"] = description.strip()
            save_data(data)
            st.success("조각 정보를 저장했습니다.")
            st.rerun()


def render_add_form(data: dict, zone_id: str) -> None:
    zone = data["zones"][zone_id]
    with st.form("add_server", clear_on_submit=True):
        st.subheader("서버 추가")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("서버명")
            private_ip = st.text_input("IP주소", placeholder="192.168.0.10")
            status = st.selectbox("상태", ["active", "standby", "maintenance", "offline"], index=0)
        with col2:
            public_ip = st.text_input("Public IP", placeholder="203.0.113.10")
            port = st.number_input("포트번호", min_value=1, max_value=65535, value=22, step=1)
            memo = st.text_input("메모", placeholder="역할, 위치, 접속 계정 힌트 등")

        submitted = st.form_submit_button("서버 저장", use_container_width=True)
        if submitted:
            errors = validate_server(name, private_ip, public_ip, int(port))
            if errors:
                for error in errors:
                    st.error(error)
                return

            zone["servers"].append(
                {
                    "id": uuid4().hex,
                    "name": name.strip(),
                    "private_ip": private_ip.strip(),
                    "public_ip": public_ip.strip(),
                    "port": int(port),
                    "status": status,
                    "memo": memo.strip(),
                    "created_at": now_text(),
                    "updated_at": now_text(),
                }
            )
            save_data(data)
            st.success("서버를 추가했습니다.")
            st.rerun()


def render_edit_form(data: dict, zone_id: str) -> None:
    zone = data["zones"][zone_id]
    servers = zone["servers"]
    if not servers:
        st.info("선택한 hexagon에 등록된 서버가 없습니다.")
        return

    st.subheader("서버 수정 및 이동")
    options = {f"{server.get('name', 'server')} ({server.get('private_ip', '-')})": server for server in servers}
    selected_label = st.selectbox("수정할 서버", list(options.keys()))
    server = options[selected_label]
    zones = current_zone_ids(data)

    with st.form("edit_server"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("서버명", value=server.get("name", ""))
            private_ip = st.text_input("IP주소", value=server.get("private_ip", ""))
            status_values = ["active", "standby", "maintenance", "offline"]
            current_status = server.get("status", "active")
            status_index = status_values.index(current_status) if current_status in status_values else 0
            status = st.selectbox("상태", status_values, index=status_index)
        with col2:
            public_ip = st.text_input("Public IP", value=server.get("public_ip", ""))
            port = st.number_input("포트번호", min_value=1, max_value=65535, value=int(server.get("port", 22)), step=1)
            target_zone = st.selectbox("이동할 hexagon 위치", zones, index=zones.index(zone_id))
        memo = st.text_area("메모", value=server.get("memo", ""), height=80)

        save_col, delete_col = st.columns(2)
        save_clicked = save_col.form_submit_button("수정/이동 저장", use_container_width=True)
        delete_clicked = delete_col.form_submit_button("삭제", use_container_width=True)

    if save_clicked:
        errors = validate_server(name, private_ip, public_ip, int(port))
        if errors:
            for error in errors:
                st.error(error)
            return

        server.update(
            {
                "name": name.strip(),
                "private_ip": private_ip.strip(),
                "public_ip": public_ip.strip(),
                "port": int(port),
                "status": status,
                "memo": memo.strip(),
                "updated_at": now_text(),
            }
        )
        if target_zone != zone_id:
            zone["servers"] = [item for item in servers if item.get("id") != server.get("id")]
            data["zones"][target_zone]["servers"].append(server)
            set_query_zone(target_zone)
        save_data(data)
        st.success("서버 정보를 저장했습니다.")
        st.rerun()

    if delete_clicked:
        zone["servers"] = [item for item in servers if item.get("id") != server.get("id")]
        save_data(data)
        st.success("서버를 삭제했습니다.")
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="tinyGW Server List", page_icon=":globe_with_meridians:", layout="wide")
    data = load_data()

    if data is None:
        render_initial_setup()
        return

    selected_zone = get_query_zone(data)
    selected = data["zones"][selected_zone]
    map_html, map_height = build_hex_map(data, selected_zone)

    st.title("tinyGW Server List")
    st.caption("Hexagon 조각으로 위치를 나누고, 조각별 서버 목록을 관리합니다.")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Hexagon 개수", int(data["grid"]["hex_count"]))
    metric_col2.metric("등록 서버", all_server_count(data))
    metric_col3.metric("선택 위치", selected_zone)
    render_grid_settings(data)

    map_col, detail_col = st.columns([1.35, 1])
    with map_col:
        st.subheader("Hexagon 위치")
        components.html(map_html, height=map_height, scrolling=False)
        st.caption("hexagon 조각을 클릭하면 해당 위치의 서버 세부 리스트가 열립니다.")

    with detail_col:
        st.subheader(f"{selected_zone} / {selected.get('name', f'Zone {selected_zone}')}")
        if selected.get("description"):
            st.write(selected["description"])
        st.metric("이 위치의 서버", len(selected["servers"]))
        render_zone_settings(data, selected_zone)

        rows = server_rows(selected["servers"])
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    form_col1, form_col2 = st.columns(2)
    with form_col1:
        render_add_form(data, selected_zone)
    with form_col2:
        render_edit_form(data, selected_zone)

    with st.expander("JSON 데이터 파일"):
        st.code(str(DATA_FILE), language="text")
        st.download_button(
            "servers.json 다운로드",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name="servers.json",
            mime="application/json",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import streamlit as st

from pulsedav import (
    ALL_SECTIONS,
    DEFAULT_INTERVAL_MINUTES,
    default_settings,
    load_settings,
    quoted_command,
    save_settings,
    send_once,
)


SECTION_LABELS = {
    "cpu": "CPU 상태",
    "network": "내부/Public IP, GW, DDNS, SSH",
    "gpu": "GPU 리스트 및 스펙",
    "disk": "HDD 공간",
    "user_services": "사용자 서비스",
    "screen": "screen 리스트",
    "crontab": "crontab",
    "docker": "docker 운영 상태",
}


def main() -> None:
    st.set_page_config(page_title="PulseDAV", page_icon=":satellite:", layout="wide")
    base = default_settings()
    settings = load_settings()

    st.title("PulseDAV")
    st.caption("호스트 상태를 Markdown 파일로 생성해 WebDAV에 주기 전송합니다.")

    col1, col2 = st.columns(2)
    with col1:
        webdav_hostname = st.text_input("WebDAV 주소", settings["webdav"]["hostname"], placeholder="https://example.com")
        webdav_root = st.text_input("WebDAV 루트 경로", settings["webdav"]["root"])
        webdav_username = st.text_input("WebDAV 사용자", settings["webdav"]["username"])
        webdav_password = st.text_input("WebDAV 비밀번호", settings["webdav"]["password"], type="password")
        verify_ssl = st.checkbox("SSL 검증", value=bool(settings["webdav"].get("verify_ssl", True)))

    with col2:
        ddns_name = st.text_input("DDNS 이름", settings["metadata"]["ddns_name"], placeholder="gw.example.net")
        ssh_port = st.text_input("SSH 포트", str(settings["metadata"]["ssh_port"]))
        intro_text = st.text_area("저장할 짧은 소개 문장", settings["metadata"]["intro_text"], height=120)
        interval_minutes = st.number_input(
            "전송 주기(분)",
            min_value=1,
            max_value=60 * 24 * 30,
            value=int(settings["schedule"].get("interval_minutes", DEFAULT_INTERVAL_MINUTES)),
            step=1,
        )

    st.subheader("포함할 정보")
    include_cols = st.columns(4)
    include_settings: dict[str, bool] = {}
    for index, key in enumerate(ALL_SECTIONS):
        with include_cols[index % 4]:
            include_settings[key] = st.checkbox(
                SECTION_LABELS[key],
                value=bool(settings.get("include", base["include"]).get(key, True)),
            )

    updated_settings = {
        "webdav": {
            "hostname": webdav_hostname.strip(),
            "root": webdav_root.strip(),
            "username": webdav_username.strip(),
            "password": webdav_password,
            "verify_ssl": verify_ssl,
        },
        "metadata": {
            "ddns_name": ddns_name.strip(),
            "ssh_port": ssh_port.strip() or "22",
            "intro_text": intro_text.strip(),
        },
        "schedule": {
            "interval_minutes": int(interval_minutes),
        },
        "include": include_settings,
    }

    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("설정 저장", use_container_width=True):
            save_settings(updated_settings)
            st.success("설정을 저장했습니다.")

    with action_col2:
        if st.button("지금 전송", use_container_width=True):
            save_settings(updated_settings)
            try:
                result = send_once(updated_settings)
            except Exception as exc:
                st.error(f"전송 실패: {exc}")
            else:
                st.success(f"전송 완료: {result['remote_path']}")
                if result["deleted_paths"]:
                    st.info("36개월 초과 파일 삭제:\n" + "\n".join(result["deleted_paths"]))
                with st.expander("업로드된 Markdown 미리보기", expanded=True):
                    st.code(result["preview"], language="markdown")

    with action_col3:
        if st.button("샘플 설정 복원", use_container_width=True):
            save_settings(base)
            st.success("기본 설정으로 저장했습니다. 화면을 새로고침하세요.")

    st.subheader("실행 예시")
    st.code(
        "\n".join(
            [
                quoted_command(["python3", "sender.py", "--once"]),
                quoted_command(["python3", "sender.py", "--loop"]),
                quoted_command(["python3", "sender.py", "--once", "--config", "/path/to/custom-settings.json"]),
                quoted_command(["python3", "sender.py", "--loop", "--config", "/path/to/custom-settings.json"]),
                quoted_command(["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "2297"]),
            ]
        ),
        language="bash",
    )

    st.subheader("부팅 자동 실행 예시")
    st.code(
        "\n".join(
            [
                "@reboot cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1",
                f"*/{max(1, min(int(interval_minutes), 59))} * * * * cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1",
            ]
        ),
        language="cron",
    )
    st.caption("첫 전송에는 `부팅한 직후` 문구가 포함되고, 이후 전송에는 `up 이후 N분`이 기록됩니다.")


if __name__ == "__main__":
    main()

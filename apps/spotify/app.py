import os
import time
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SPOTIFY_ACCOUNTS_URL = "https://accounts.spotify.com"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
DISCOGS_API_URL = "https://api.discogs.com"
DEFAULT_REDIRECT_URI = "http://localhost:8501"
DEFAULT_PAGE_SIZE = 20


def init_session_state() -> None:
    defaults = {
        "spotify_token": None,
        "spotify_refresh_token": None,
        "spotify_token_expires_at": 0,
        "spotify_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def rerun() -> None:
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    else:
        st.rerun()


def get_env(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback).strip()


def build_spotify_auth_url(client_id: str, redirect_uri: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "user-library-read",
        }
    )
    return f"{SPOTIFY_ACCOUNTS_URL}/authorize?{query}"


def exchange_code_for_token(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict[str, Any]:
    response = requests.post(
        f"{SPOTIFY_ACCOUNTS_URL}/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_spotify_token(client_id: str, client_secret: str, refresh_token: str) -> dict[str, Any]:
    response = requests.post(
        f"{SPOTIFY_ACCOUNTS_URL}/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def store_spotify_token(token_data: dict[str, Any]) -> None:
    st.session_state.spotify_token = token_data.get("access_token")
    if token_data.get("refresh_token"):
        st.session_state.spotify_refresh_token = token_data["refresh_token"]
    expires_in = int(token_data.get("expires_in", 0))
    st.session_state.spotify_token_expires_at = int(time.time()) + expires_in - 30


def ensure_spotify_token(client_id: str, client_secret: str, redirect_uri: str) -> None:
    code = st.query_params.get("code")
    if isinstance(code, list):
        code = code[0]

    if code and not st.session_state.spotify_token:
        token_data = exchange_code_for_token(client_id, client_secret, redirect_uri, code)
        store_spotify_token(token_data)
        st.query_params.clear()
        rerun()

    now = int(time.time())
    if st.session_state.spotify_token and now < st.session_state.spotify_token_expires_at:
        return

    if st.session_state.spotify_refresh_token:
        token_data = refresh_spotify_token(
            client_id, client_secret, st.session_state.spotify_refresh_token
        )
        store_spotify_token(token_data)


def spotify_get(url: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(show_spinner=False, ttl=300)
def load_saved_tracks(token: str, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset = 0
    while len(items) < limit:
        page_size = min(50, limit - len(items))
        payload = spotify_get(
            f"{SPOTIFY_API_URL}/me/tracks",
            token,
            params={"limit": page_size, "offset": offset},
        )
        page_items = payload.get("items", [])
        if not page_items:
            break
        items.extend(page_items)
        offset += len(page_items)
    return items


@st.cache_data(show_spinner=False, ttl=1800)
def search_discogs(artist: str, track: str, token: str, user_agent: str) -> dict[str, Any]:
    response = requests.get(
        f"{DISCOGS_API_URL}/database/search",
        params={"artist": artist, "track": track, "type": "release", "per_page": 5, "token": token},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data


def render_spotify_embed(track_id: str) -> None:
    html = f"""
    <iframe
        src="https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
        width="100%"
        height="352"
        frameborder="0"
        allowfullscreen=""
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        loading="lazy">
    </iframe>
    """
    components.html(html, height=370)


def format_track_label(item: dict[str, Any]) -> str:
    track = item["track"]
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    return f'{track["name"]} - {artists}'


def render_discogs_panel(track: dict[str, Any], discogs_token: str, discogs_user_agent: str) -> None:
    artists = track.get("artists", [])
    primary_artist = artists[0]["name"] if artists else ""
    with st.spinner("Discogs 정보를 조회하는 중입니다..."):
        results = search_discogs(primary_artist, track["name"], discogs_token, discogs_user_agent)

    release_items = results.get("results", [])
    if not release_items:
        st.info("Discogs에서 일치하는 릴리스를 찾지 못했습니다.")
        return

    top_release = release_items[0]
    col1, col2 = st.columns([1, 2])
    with col1:
        cover = top_release.get("cover_image")
        if cover:
            st.image(cover, use_container_width=True)
    with col2:
        st.subheader("Discogs 매칭 정보")
        st.write(f"제목: {top_release.get('title', '-')}")
        st.write(f"연도: {top_release.get('year', '-')}")
        genres = ", ".join(top_release.get("genre", [])) or "-"
        styles = ", ".join(top_release.get("style", [])) or "-"
        st.write(f"장르: {genres}")
        st.write(f"스타일: {styles}")
        if top_release.get("country"):
            st.write(f"국가: {top_release['country']}")
        if top_release.get("resource_url"):
            st.markdown(f"[Discogs 상세 링크]({top_release['resource_url']})")


def main() -> None:
    st.set_page_config(page_title="Spotify + Discogs Remote Player", layout="wide")
    init_session_state()
    st.title("Spotify 좋아요 음악 원격 플레이어")
    st.caption("Spotify 저장 트랙을 불러와 재생하고, Discogs 메타데이터를 함께 보여줍니다.")
    with st.expander("사용 방법", expanded=True):
        st.markdown(
            """
            ### 1. Spotify 연결 정보 입력 방법
            1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)에 로그인합니다.
            2. `Create app`으로 앱을 만든 뒤 `Client ID`와 `Client Secret`을 확인합니다.
            3. 앱 설정의 Redirect URI에 이 앱 주소를 등록합니다.
               예: `http://localhost:8501`
            4. 왼쪽 `API 설정`에서 아래 값을 입력합니다.
               `Spotify Client ID`: Spotify Developer Dashboard의 Client ID
               `Spotify Client Secret`: Spotify Developer Dashboard의 Client Secret
               `Spotify Redirect URI`: Spotify 앱 설정에 등록한 Redirect URI와 동일한 값
            5. `Spotify 로그인` 버튼을 눌러 인증하면 저장한 좋아요 음악을 불러올 수 있습니다.

            ### 2. Discogs ID, URL, 키 획득 및 입력 방법
            1. [Discogs 개발자 설정](https://www.discogs.com/settings/developers)에 로그인해 Personal Access Token을 발급받습니다.
            2. 이 앱에서 직접 입력하는 Discogs 값은 아래 두 개입니다.
               `Discogs Token`: 발급받은 Personal Access Token
               `Discogs User-Agent`: 요청 식별 문자열. 예: `BerePiSpotifyApp/1.0`
            3. Discogs 검색 URL은 앱이 자동으로 사용합니다.
               기본 API URL: `https://api.discogs.com`
            4. Discogs 릴리스 ID와 상세 URL도 앱이 검색 결과에서 자동으로 찾습니다.
               별도 입력이 필요하지 않으며, 조회 후 화면에 표시되는 상세 링크에서 확인할 수 있습니다.
            """
        )

    with st.sidebar:
        st.header("API 설정")
        spotify_client_id = st.text_input(
            "Spotify Client ID",
            value=get_env("SPOTIFY_CLIENT_ID"),
            help="Spotify Developer Dashboard에서 발급받은 Client ID를 입력합니다.",
        )
        spotify_client_secret = st.text_input(
            "Spotify Client Secret",
            value=get_env("SPOTIFY_CLIENT_SECRET"),
            type="password",
            help="Spotify Developer Dashboard의 Client Secret입니다. 비밀번호처럼 숨김 처리됩니다.",
        )
        spotify_redirect_uri = st.text_input(
            "Spotify Redirect URI",
            value=get_env("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI),
            help="Spotify 앱 설정에 등록한 Redirect URI와 동일하게 입력해야 합니다.",
        )
        discogs_token = st.text_input(
            "Discogs Token",
            value=get_env("DISCOGS_TOKEN"),
            type="password",
            help="Discogs developers 설정에서 발급받은 Personal Access Token을 입력합니다.",
        )
        discogs_user_agent = st.text_input(
            "Discogs User-Agent",
            value=get_env("DISCOGS_USER_AGENT", "BerePiWebdavMusicApp/1.0"),
            help="Discogs 요청 식별용 문자열입니다. 앱 이름/버전 형식을 권장합니다.",
        )
        max_tracks = st.slider("조회할 좋아요 트랙 수", min_value=10, max_value=100, value=DEFAULT_PAGE_SIZE, step=10)

    if not spotify_client_id or not spotify_client_secret:
        st.warning("Spotify Client ID/Secret을 입력해야 좋아요 음악을 조회할 수 있습니다.")
        st.stop()

    auth_url = build_spotify_auth_url(spotify_client_id, spotify_redirect_uri)
    st.link_button("Spotify 로그인", auth_url)

    try:
        ensure_spotify_token(spotify_client_id, spotify_client_secret, spotify_redirect_uri)
    except requests.HTTPError as exc:
        st.error(f"Spotify 인증 처리 중 오류가 발생했습니다: {exc}")
        st.stop()

    if not st.session_state.spotify_token:
        st.info("Spotify 로그인을 마치면 이 페이지로 돌아와 저장한 음악 목록을 확인할 수 있습니다.")
        st.stop()

    try:
        saved_tracks = load_saved_tracks(st.session_state.spotify_token, max_tracks)
    except requests.HTTPError as exc:
        st.error(f"Spotify 저장 트랙 조회 실패: {exc}")
        st.stop()

    if not saved_tracks:
        st.info("좋아요 표시한 Spotify 트랙이 없거나 조회되지 않았습니다.")
        st.stop()

    labels = [format_track_label(item) for item in saved_tracks]
    selected_label = st.selectbox("재생할 음악 선택", labels, index=0)
    selected_item = saved_tracks[labels.index(selected_label)]
    track = selected_item["track"]

    left, right = st.columns([2, 1])
    with left:
        st.subheader(track["name"])
        artists = ", ".join(artist["name"] for artist in track.get("artists", []))
        st.write(f"아티스트: {artists}")
        st.write(f"앨범: {track.get('album', {}).get('name', '-')}")
        st.write(f"Spotify 링크: {track.get('external_urls', {}).get('spotify', '-')}")
        render_spotify_embed(track["id"])
    with right:
        album_images = track.get("album", {}).get("images", [])
        if album_images:
            st.image(album_images[0]["url"], use_container_width=True)
        st.metric("인기 점수", track.get("popularity", 0))
        if track.get("preview_url"):
            st.audio(track["preview_url"])
        else:
            st.caption("Spotify API preview_url이 없는 곡은 Embed 플레이어로 재생합니다.")

    if discogs_token:
        try:
            render_discogs_panel(track, discogs_token, discogs_user_agent)
        except requests.HTTPError as exc:
            st.error(f"Discogs 조회 실패: {exc}")
    else:
        st.info("Discogs Token을 입력하면 아티스트/릴리스 정보를 함께 표시합니다.")


if __name__ == "__main__":
    main()

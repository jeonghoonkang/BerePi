# Spotify + Discogs Streamlit Player

이 앱은 Spotify에 좋아요 표시한 트랙을 원격 API로 조회하고, Spotify Embed로 재생하며, Discogs에서 관련 릴리스 정보를 함께 보여준다.

## 준비

1. Spotify Developer Dashboard에서 앱을 만든다.
2. Redirect URI에 `http://localhost:8501` 또는 사용할 Streamlit 주소를 등록한다.
3. Discogs에서 Personal Access Token을 발급받는다.
4. `.env.example`을 참고해 `apps/webdav/.env` 파일을 만든다.

## 실행

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/webdav
pip install -r requirements.txt
streamlit run app.py
```

## 동작 방식

- Spotify OAuth로 `user-library-read` 권한을 받아 좋아요 트랙을 읽는다.
- 선택한 트랙은 Streamlit 안에서 Spotify Embed iframe으로 재생한다.
- `preview_url`이 제공되는 트랙은 추가로 Streamlit 오디오 플레이어도 표시한다.
- Discogs 검색 API로 아티스트/곡명을 기준으로 매칭 릴리스를 찾아 메타데이터를 보여준다.

## 제한 사항

- Spotify 전체 음원 스트리밍은 Spotify Embed 또는 공식 플레이어 정책 범위 내에서만 가능하다.
- 모든 트랙에 `preview_url`이 제공되지는 않는다.
- Discogs 검색 결과는 완전 일치가 아닐 수 있어 가장 유사한 첫 결과를 우선 표시한다.

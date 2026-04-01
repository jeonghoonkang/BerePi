# Spotify + Discogs Remote Player

Streamlit 기반 앱으로 Spotify의 좋아요 트랙을 불러와 재생하고, Discogs 메타데이터를 함께 조회합니다.

## 필요한 환경 변수

`apps/spotify/.env` 파일에 아래 값을 설정해서 사용할 수 있습니다.

```env
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://localhost:8501
DISCOGS_TOKEN=
DISCOGS_USER_AGENT=BerePiWebdavMusicApp/1.0
```

기본 예시는 [`.env.example`](/Users/tinyos/devel_opment/BerePi/apps/spotify/.env.example)에 있습니다.

## 키 발급 방법

### 1. `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)에 로그인합니다.
2. `Create app`을 눌러 새 앱을 생성합니다.
3. 생성한 앱 상세 화면에서 `Client ID`를 확인합니다.
4. `View client secret`을 눌러 `Client Secret`을 확인합니다.

이 두 값은 Streamlit 앱의 Spotify OAuth 인증과 저장 트랙 조회에 사용됩니다.

### 2. `SPOTIFY_REDIRECT_URI`

1. 같은 Spotify 앱 설정 화면에서 `Edit settings`를 엽니다.
2. `Redirect URIs` 항목에 이 앱이 열릴 주소를 추가합니다.
3. 로컬 실행 시 일반적으로 `http://localhost:8501`을 사용합니다.

주의:
`SPOTIFY_REDIRECT_URI` 값은 Spotify Developer Dashboard에 등록한 값과 완전히 같아야 합니다. 다르면 로그인 후 토큰 교환이 실패합니다.

### 3. `DISCOGS_TOKEN`

1. [Discogs Developers Settings](https://www.discogs.com/settings/developers)에 로그인합니다.
2. `Generate new token` 또는 Personal Access Token 발급 메뉴를 사용해 토큰을 생성합니다.
3. 생성된 토큰 값을 `DISCOGS_TOKEN`에 넣습니다.

이 값은 아티스트/트랙명 기준으로 Discogs 릴리스 검색 API를 호출할 때 사용됩니다.

### 4. `DISCOGS_USER_AGENT`

Discogs API는 요청 식별용 `User-Agent` 헤더를 요구합니다. 보통 아래 형식으로 지정하면 됩니다.

```text
앱이름/버전
```

예시:

```text
BerePiWebdavMusicApp/1.0
```

## 사용 방법

### 1. 환경 변수 파일 준비

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/spotify
cp .env.example .env
```

그 다음 `.env`에 발급받은 값을 입력합니다.

### 2. 의존성 설치

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/spotify
pip install -r requirements.txt
```

### 3. 앱 실행

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/spotify
streamlit run app.py
```

브라우저에서 보통 [http://localhost:8501](http://localhost:8501)로 열립니다.

### 4. Spotify 로그인

1. 사이드바에서 `Spotify Client ID`, `Spotify Client Secret`, `Spotify Redirect URI`가 올바른지 확인합니다.
2. `Spotify 로그인` 버튼을 눌러 Spotify 인증을 진행합니다.
3. 인증이 끝나면 이 페이지로 돌아오고, 저장한 좋아요 트랙 목록을 조회할 수 있습니다.

### 5. Discogs 조회

1. 사이드바에 `Discogs Token`을 입력합니다.
2. 필요하면 `Discogs User-Agent`도 수정합니다.
3. 트랙을 선택하면 Discogs 검색 결과 중 상위 릴리스 정보를 함께 표시합니다.

## 환경 변수별 실제 사용처

### `SPOTIFY_CLIENT_ID`

- Spotify OAuth 로그인 URL 생성
- 인가 코드로 액세스 토큰 교환
- 리프레시 토큰 갱신

### `SPOTIFY_CLIENT_SECRET`

- 인가 코드로 액세스 토큰 교환
- 리프레시 토큰 갱신

### `SPOTIFY_REDIRECT_URI`

- Spotify 로그인 완료 후 다시 돌아올 주소
- 인가 코드 토큰 교환 시 검증용 값

### `DISCOGS_TOKEN`

- Discogs `/database/search` API 호출 인증값

### `DISCOGS_USER_AGENT`

- Discogs API 요청 헤더 식별값

## 참고

- Spotify 좋아요 트랙 조회에는 `user-library-read` 권한이 사용됩니다.
- Discogs 토큰이 없으면 Spotify 재생 기능은 동작하지만 Discogs 메타데이터는 표시되지 않습니다.
- 로컬 주소를 바꾸면 Spotify Dashboard의 Redirect URI와 `.env` 값을 함께 수정해야 합니다.

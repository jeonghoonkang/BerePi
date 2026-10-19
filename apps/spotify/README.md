# BerePi Music — Spotify + HTTP 파일 플레이어

Spotify 데스크톱/모바일 앱 없이 브라우저에서 계정의 좋아요 곡, 공개/비공개 및 공동 재생목록을 조회하고 Web Playback SDK로 재생합니다. 자신의 HTTP 서버 음악 파일도 같은 큐에 추가합니다. 각 항목은 `Spotify` / `HTTP 파일`로 표시되며, 소스 전환 시 이전 플레이어를 먼저 멈춥니다. 이전/다음, 일시정지, 곡 종료 후 다음 항목 재생을 지원합니다.

## 1. 준비 사항

- Python 3.10 이상과 인터넷 연결이 필요합니다.
- Spotify 음악을 끝까지 들으려면 Spotify Premium 계정이 필요합니다. Spotify 앱을 설치하거나 실행할 필요는 없습니다.
- Spotify 개발자 앱의 Client ID / Client Secret을 준비합니다. **Spotify 계정의 아이디·비밀번호와 다른 값**입니다.
- DRM/Encrypted Media를 지원하는 브라우저를 사용하고, 보호된 콘텐츠 재생을 허용합니다.
- 처음에는 앱을 실행하는 컴퓨터에서 `http://127.0.0.1:8501`로 접속해 설정하세요. 다른 PC·휴대폰에서 접속하려면 아래 원격 접속 설정이 필요합니다.
- HTTP 음악 파일만 재생한다면 Spotify 계정과 개발자 앱 설정은 생략할 수 있습니다.

## 2. Spotify 개발자 앱 만들기

### 2-1. Dashboard 접속 및 앱 생성

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)에 접속합니다.
2. 연결하려는 Spotify 계정으로 로그인합니다. 처음 접속하면 개발자 이용약관 등의 안내를 확인합니다.
3. **Create app**을 누릅니다. 이미 개인용 앱이 있으면 해당 앱을 선택해 설정할 수도 있습니다. 생성 가능 여부는 계정에 적용되는 Spotify 개발자 정책을 따릅니다.
4. 다음 예시를 참고해 입력합니다. Dashboard 메뉴 이름은 변경될 수 있습니다.

   | 항목 | 입력 예시 |
   | --- | --- |
   | App name | `BerePi Music` |
   | App description | `Personal Spotify and HTTP music player` |
   | Website (입력하는 경우) | 실제 운영하는 웹사이트 주소 |
   | Redirect URI | `http://127.0.0.1:8501/callback` |
   | 사용할 API / SDK 선택란이 있는 경우 | `Web API`, `Web Playback SDK` |

5. 약관을 확인하고 저장합니다.

### 2-2. Client ID와 Client Secret 확인

1. 생성한 앱을 열고 **Settings**로 이동합니다.
2. **Client ID** 값을 복사합니다.
3. **View client secret** 등의 표시 버튼을 눌러 **Client Secret**을 확인합니다.
4. 두 값을 아래 3절의 `.env`에 입력합니다. 웹 페이지의 로그인창에 입력하는 값이 아닙니다.

Client Secret은 비밀키입니다. `.env`를 Git에 커밋하거나 다른 사람에게 공유하지 마세요. 유출되면 Dashboard에서 키를 재발급하고 `.env`도 변경해야 합니다.

### 2-3. Redirect URI 등록

앱의 **Settings → Redirect URIs**에 다음 주소를 추가하고 저장합니다.

```text
http://127.0.0.1:8501/callback
```

이 주소는 로그인 승인 후 Spotify가 사용자를 이 플레이어로 돌려보내는 주소입니다. **Dashboard 등록값과 `.env`의 `SPOTIFY_REDIRECT_URI`가 정확하게 일치**해야 합니다. 프로토콜, 호스트, 포트, `/callback` 경로와 끝의 슬래시 유무까지 확인하세요.

- 로컬에서는 `localhost` 대신 명시적 loopback IP인 `127.0.0.1`을 사용합니다.
- 브라우저에서도 `http://127.0.0.1:8501`로 시작하세요. `localhost`로 로그인한 뒤 `127.0.0.1`로 돌아오면 로그인 검증 쿠키가 연결되지 않을 수 있습니다.
- `/callback`을 브라우저에서 직접 여는 것이 아닙니다. 앱의 **Spotify 로그인** 버튼에서 시작해야 합니다.
- 예전 설정값 `http://localhost:8501`은 현재 앱의 콜백 주소로 바꿔야 합니다.

공식 규칙: [Redirect URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

### 2-4. 사용할 Spotify 계정 등록

Development Mode에서는 허용된 사용자만 사용할 수 있습니다.

1. 앱의 **User Management**, **Users and Access** 등 사용자 관리 메뉴를 확인합니다.
2. 사용할 Spotify 계정이 허용되어 있는지 확인하고, 필요한 경우 해당 계정의 이름과 이메일로 추가합니다.
3. 이후 플레이어의 로그인 화면에서도 같은 계정으로 로그인합니다.

개발 모드에는 Premium 요건, 허용 사용자 수 및 API 접근 제한이 적용됩니다. 생성 또는 사용자 추가가 막히면 Dashboard 안내와 [공식 Development Mode 변경 안내](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)를 확인하세요.

## 3. 설치 및 .env 설정

터미널에서 실행합니다.

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/spotify
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

처음 설정할 때만 예제 파일을 복사합니다. 이미 `.env`가 있다면 기존 파일을 편집하세요.

```bash
cp .env.example .env
```

`.env`를 텍스트 편집기로 열어 다음과 같이 설정합니다. 아래 키 값은 예시이므로 실제 Dashboard 값으로 바꿔야 합니다.

```dotenv
SPOTIFY_CLIENT_ID=여기에_Client_ID
SPOTIFY_CLIENT_SECRET=여기에_Client_Secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8501/callback
SESSION_SECRET=여기에_임의의_긴_문자열
HOST=127.0.0.1
PORT=8501
COOKIE_SECURE=0
```

| 설정 | 의미 |
| --- | --- |
| `SPOTIFY_CLIENT_ID` | Dashboard에서 발급받은 앱 ID |
| `SPOTIFY_CLIENT_SECRET` | Dashboard에서 발급받은 앱 비밀키. 서버에서만 사용 |
| `SPOTIFY_REDIRECT_URI` | Dashboard에 등록한 로그인 콜백 주소 |
| `SESSION_SECRET` | 이 앱의 쿠키 서명 키. Spotify에서 발급하는 값이 아님 |
| `HOST` | 서버가 요청을 받을 주소. 기본은 로컬 컴퓨터만 허용 |
| `PORT` | 앱 서버 포트. 바꾸면 접속 주소와 Redirect URI도 함께 변경 |
| `COOKIE_SECURE` | 로컬 HTTP는 `0`, HTTPS 배포는 `1` |

`SESSION_SECRET`에 사용할 임의 값은 다음 명령으로 생성할 수 있습니다. 출력된 값을 복사해 넣으세요.

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

`SESSION_SECRET`을 비우면 실행할 때 임의 키가 생성됩니다. `.env`를 수정한 뒤에는 서버를 종료하고 다시 실행해야 반영됩니다.

## 4. 실행하고 Spotify 계정 연결하기

```bash
source .venv/bin/activate
python app.py
```

1. 서버 터미널을 열어 둔 상태에서 [http://127.0.0.1:8501](http://127.0.0.1:8501)에 접속합니다.
2. **Spotify 로그인**을 누릅니다.
3. Spotify 공식 로그인 페이지에서 자신의 계정으로 로그인합니다.
4. 계정 정보, 좋아요 곡, 재생목록 조회 및 재생 관련 권한 요청을 확인하고 승인합니다.
5. 자동으로 BerePi Music으로 돌아오면 `연결됨: 계정명`이 표시되는지 확인합니다.
6. **브라우저 플레이어 연결**을 누릅니다.
7. `브라우저 플레이어 연결 완료`가 표시될 때까지 기다립니다.
8. **좋아요 곡** 또는 **내 재생목록**을 누릅니다. 재생목록을 선택하면 해당 목록의 곡이 표시됩니다.
9. 곡의 `[Spotify] + 제목` 버튼으로 큐에 추가합니다. 목록은 **더 불러오기**로 추가 조회합니다.
10. **재생 큐**에서 원하는 곡을 눌러 재생합니다. 곡 추가만으로 즉시 재생되지는 않습니다.

Spotify 앱을 켜거나 별도 기기를 선택할 필요가 없습니다. `BerePi Browser`라는 브라우저 재생 장치가 만들어지고, 현재 브라우저에서 소리가 납니다. 브라우저 자동재생 정책에 따라 직접 연결·재생 버튼을 눌러야 합니다.

앱이 요청하는 권한은 다음과 같습니다. 코드에서 자동 요청하므로 따로 입력하지 않습니다.

| 권한 | 사용 목적 |
| --- | --- |
| `streaming` | 브라우저 SDK 재생 |
| `user-read-email`, `user-read-private` | SDK에 필요한 계정 정보 및 프로필 확인 |
| `user-library-read` | 좋아요 곡 조회 |
| `playlist-read-private`, `playlist-read-collaborative` | 비공개·공동 재생목록 조회 |
| `user-read-playback-state`, `user-modify-playback-state` | 재생 상태 및 브라우저 장치 재생 제어 |

계정·지역·개발자 API 정책에 따라 일부 재생목록 또는 곡에 접근하지 못할 수 있습니다. 삭제된 곡, Spotify 로컬 파일 및 재생 불가 곡은 제외합니다. 권한 구성이 바뀌면 다시 로그인해 승인해야 합니다.

기존 Streamlit 버전과 Discogs 조회 기능은 `legacy_streamlit.py`에 보관했습니다. 현재 버전은 `streamlit run`이 아닌 `python app.py`로 실행합니다. 기존 버전 실행에는 `streamlit`을 별도로 설치해야 합니다.

## 내 HTTP 음악 서버

- **파일 URL**: `http://server/music/song.mp3` 등을 입력하고 추가합니다. 확장자가 없는 서명된 다운로드 URL도 입력할 수 있습니다.
- **폴더 URL**: Apache/nginx의 HTML 디렉토리 목록에서 하위 폴더 및 MP3/M4A/AAC/WAV/OGG/FLAC 링크를 읽습니다. 브라우저가 폴더를 읽을 수 있도록 음악 서버에서 이 앱 출처에 대한 CORS를 허용해야 합니다. 직접 파일 재생에는 일반적으로 목록 조회용 CORS가 필요하지 않습니다.
- 파일은 브라우저가 서버에서 직접 스트리밍합니다. 앱 서버가 임의 URL을 프록시하지 않습니다. 브라우저에서 음악 서버에 접속 가능해야 합니다.
- HTTPS 앱에서 HTTP 음악은 혼합 콘텐츠 정책으로 차단/업그레이드될 수 있습니다. 원격 배포에서는 음악 서버도 HTTPS로 제공하세요.
- 서버의 올바른 Content-Type과 Range 응답은 원활한 재생 및 탐색에 도움이 됩니다. 코덱 지원은 브라우저에 따라 다릅니다. 인증정보가 들어간 URL은 받지 않습니다. 인증 서버는 브라우저 접근 가능한 인증 방식 또는 만료형 서명 URL을 사용하세요.
- Spotify 항목은 SDK, 일반 파일은 HTML audio로 처리합니다. Spotify 콘텐츠를 MP3로 다운로드하거나 변환하지 않습니다. HTTP 재생은 Spotify 로그인 없이 가능합니다.

### HTTP 음악 재생 순서

1. 음악 파일 URL을 브라우저에서 직접 열어 접근 가능한지 확인합니다.
2. **파일 URL**에 `http://서버주소/music/song.mp3`를 입력하고 **파일 추가**를 누릅니다.
3. 큐에 `[HTTP 파일]`로 표시되는지 확인하고 해당 항목을 눌러 재생합니다.
4. 폴더 단위로 탐색하려면 **폴더 URL**에 `http://서버주소/music/`를 입력하고 **폴더 열기**를 누릅니다.
5. 폴더 목록의 `[HTTP 파일] + 제목`으로 곡을 추가합니다. Spotify 곡과 섞어 큐에 넣을 수 있습니다.

폴더 열기에는 서버의 HTML 디렉토리 목록과 CORS 설정이 필요합니다. 목록 기능 없이 직접 파일 URL만 넣어 재생할 수도 있습니다. HTTP 파일의 재생·시간 이동·음량은 화면 아래 오디오 컨트롤로 조절합니다. 공통 **재생 / 일시정지** 버튼은 현재 소스에 맞춰 동작합니다.

## 원격 PC·휴대폰에서 접속하기

`127.0.0.1`은 브라우저를 사용하는 기기 자신을 가리킵니다. 서버가 Raspberry Pi에 있고 휴대폰에서 접속한다면 `127.0.0.1` 콜백을 사용할 수 없습니다.

1. 서버 앞에 HTTPS 리버스 프록시를 구성하고 실제 도메인을 준비합니다.
2. Dashboard에 `https://music.example.com/callback`처럼 실제 도메인의 콜백을 등록합니다.
3. `.env`도 다음 예시처럼 변경합니다.

```dotenv
SPOTIFY_REDIRECT_URI=https://music.example.com/callback
COOKIE_SECURE=1
```

4. 프록시가 앱의 `127.0.0.1:8501`로 전달하도록 설정합니다. 프록시가 별도 호스트에 있을 때만 네트워크 구성에 맞춰 `HOST`를 변경합니다.
5. 서버를 재시작한 뒤 해당 HTTPS 도메인으로 접속해 다시 로그인합니다.
6. 음악 서버 파일도 HTTPS로 접근 가능하게 구성합니다.

단순히 `HOST=0.0.0.0`으로 바꾸고 `http://서버IP:8501`로 접속하는 것만으로는 Spotify의 HTTPS·보안 컨텍스트 요구를 충족하지 못합니다.

## 문제 해결

| 증상 | 확인할 사항 |
| --- | --- |
| `invalid_client` 또는 인증 실패 | Client ID와 Secret이 같은 개발자 앱의 값인지 확인하고 서버 재시작 |
| Redirect URI 오류 | Dashboard와 `.env`의 주소·포트·`/callback`·끝 슬래시를 비교 |
| 로그인 검증 실패 | `127.0.0.1`과 `localhost`를 섞지 않았는지 확인. 서버 재시작 후에는 처음부터 다시 로그인 |
| 로그인을 취소했다는 메시지 | 앱 첫 화면에서 다시 Spotify 로그인 후 권한 승인 |
| 로그인 후 403 / 사용자 미등록 | 실제 로그인 계정의 개발 모드 허용 여부와 계정/API 제한 확인 |
| Premium / account 오류 | 재생 계정의 Premium 상태 확인 |
| 브라우저 플레이어 연결 실패 | HTTPS 또는 로컬 loopback 접속, DRM 허용 여부, SDK 네트워크 차단 확인 |
| 재생 장치가 없다는 오류 | 브라우저 플레이어를 연결하고 완료 메시지 확인 후 큐의 곡을 다시 클릭 |
| 목록은 보이지만 소리가 안 남 | 곡을 큐에 추가한 뒤 큐 항목 클릭, 탭 음소거·기기 음량·보호된 콘텐츠 설정 확인 |
| 401 / 로그인 만료 | Spotify 로그아웃 후 다시 로그인. 서버 재시작 시 재인증 필요 |
| 429 | Spotify 호출 제한. 잠시 기다린 뒤 다시 시도 |
| HTTP 파일 재생 실패 | 브라우저에서 URL 직접 확인, 파일 접근 권한·지원 코덱·혼합 콘텐츠 차단 확인 |
| 파일은 재생되지만 폴더 열기 실패 | 디렉토리 인덱스 활성화와 앱 출처에 대한 CORS 허용 확인 |
| 새로고침 후 큐가 사라짐 | 현재 큐는 탭 메모리에만 유지됨. 필요한 곡을 다시 추가 |
| `ModuleNotFoundError` | `.venv` 활성화 후 `pip install -r requirements.txt` 실행 |
| 포트가 이미 사용 중 | 기존 서버를 종료하거나 `PORT`, 접속 URL, Dashboard와 `.env`의 Redirect URI를 함께 변경 |

## 세션 / 배포

Access/refresh token은 서버 메모리에만 보관하며 브라우저 쿠키에는 세션 식별자만 저장합니다. SDK에는 단기 access token만 전달합니다. OAuth state, 10분 로그인 만료, 변경 요청 CSRF 검증을 적용합니다. 토큰은 자동 갱신하며 세션은 24시간 후 만료됩니다. 서버 재시작 후 재로그인이 필요합니다. 큐는 현재 탭 메모리에만 유지됩니다.

기본은 로컬 개인용 단일 프로세스 서버입니다. 원격 사용 시 HTTPS 리버스 프록시, 적절한 접근 제한을 구성하고 `SESSION_SECRET`을 충분히 긴 임의 값으로, `COOKIE_SECURE=1`, `SPOTIFY_REDIRECT_URI=https://실제주소/callback`으로 설정하세요. 필요 시 `HOST=0.0.0.0`을 사용합니다. 다중 worker는 메모리 토큰 저장소를 공유하지 않으므로 Redis 같은 공용 세션 저장소로 교체해야 합니다. Flask 내장 서버는 개발용입니다.

검증: `python -m unittest discover -s tests -v`
실제 Spotify 계정 재생 및 HTTP 서버 연동은 사용자 자격증명과 서버에서 별도로 확인해야 합니다.

## 공식 문서

- [개발자 앱 생성 및 설정](https://developer.spotify.com/documentation/web-api/concepts/apps)
- [Web Playback SDK / Premium 조건](https://developer.spotify.com/documentation/web-playback-sdk)
- [Redirect URI 규칙](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)
- [Development Mode 변경](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)

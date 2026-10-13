# BerePi Photo Browser

시스템 디렉토리의 JPG/JPEG, PNG, GIF, MP4를 웹에서 탐색하는 읽기 전용 앱입니다.

- 경로 직접 입력, 상위 폴더 및 하위 폴더 이동
- 날짜별 그룹과 날짜 필터 (**서버 현지 시간의 파일 수정일 기준**, EXIF 촬영일 아님)
- 하위 폴더 포함 재귀 검색, 이미지/동영상 필터
- 이미지/GIF 원본 미리보기, MP4 재생 및 구간 요청(Range) 지원
- 클릭해서 확대, 좌우 버튼/방향키로 이동, Esc로 닫기
- 100개씩 표시, 검색 결과 최대 20,000개 (도달 시 안내)

## 1. 간단한 독립 서버

저장소 루트에서 실행합니다. Python 3.10 이상이 필요합니다.

```bash
python3 -m venv apps/photo_browser/.venv
apps/photo_browser/.venv/bin/pip install -r apps/photo_browser/requirements.txt
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py --directory "$HOME/Pictures"
```

브라우저: <http://127.0.0.1:7081/>

다른 기기에서도 연결하려면 `--host 0.0.0.0`을 추가합니다. 포트는 `--port 7081`로 변경할 수 있습니다. `--directory` 폴더는 실제 존재하는 경로를 지정하세요. 미지정 시 사용자 홈에서 시작합니다.

```bash
apps/photo_browser/.venv/bin/python apps/photo_browser/app.py \
  --host 0.0.0.0 --port 7081 --root /data --directory /data/photos
```

`--root` 기본값은 `/`이므로 앱 실행 계정이 읽을 수 있는 시스템 전체를 탐색할 수 있습니다. 공유 서버에서는 공개할 폴더를 `--root`로 제한하세요. 심볼릭 링크로 루트 밖에 접근하는 것도 차단합니다. 재귀 검색에서는 디렉토리 심볼릭 링크를 따라가지 않습니다. 파일 변경/삭제 기능은 없습니다. 자체 로그인 기능이 없으므로 외부 공개 시 Apache 인증 또는 네트워크 접근 제한을 사용하세요.

## 2. 기존 Apache 7080 서버 활용

Apache는 웹페이지 요청을 Python 앱으로 전달합니다. **정적 HTML 복사만으로는 시스템 폴더를 스캔할 수 없으므로 Python 서버도 함께 실행해야 합니다.** 기존 Apache의 포트나 DocumentRoot를 변경할 필요가 없습니다.

먼저 위의 독립 서버를 `127.0.0.1:7081`에서 실행합니다. 지속 운영에는 같은 가상환경에 Gunicorn을 설치해 사용할 수 있습니다 (Linux/macOS).

```bash
apps/photo_browser/.venv/bin/pip install gunicorn
cd apps/photo_browser
PHOTO_BROWSER_ROOT=/data PHOTO_BROWSER_START=/data/photos \
  .venv/bin/gunicorn --bind 127.0.0.1:7081 --workers 2 --threads 4 --timeout 120 'app:create_app()'
```

Apache의 **기존 7080 VirtualHost 블록 안에** 다음을 추가합니다. 같은 내용은 `apache/photo-browser.conf`에도 있습니다. 해당 파일을 VirtualHost 안에서 절대 경로로 `Include`해도 됩니다.

```apache
RedirectMatch 302 ^/photo-browser$ /photo-browser/
ProxyPass        /photo-browser/ http://127.0.0.1:7081/
ProxyPassReverse /photo-browser/ http://127.0.0.1:7081/
```

기존에 `ProxyPass / ...` 규칙이 있다면 위 규칙을 그보다 먼저 배치하세요. `proxy`, `proxy_http`, `alias` 모듈이 필요합니다. Debian/Ubuntu에서는:

```bash
sudo a2enmod proxy proxy_http alias
sudo apachectl configtest
sudo systemctl reload apache2
```

macOS/Homebrew 등에서는 Apache 설정의 해당 `LoadModule`을 활성화하고, 해당 설치 방식의 재시작 명령을 사용하세요. 설정 문법 검사는 `apachectl configtest`입니다.

접속: `http://서버주소:7080/photo-browser/`

페이지의 경로는 **Python 서버가 실행되는 시스템의 경로**입니다. 접속한 PC의 디렉토리는 서버에서 볼 수 없습니다. 파일 읽기 권한 역시 Python 실행 계정 기준입니다. Apache 설정 예시만 제공하며 시스템 설정을 자동 변경하지 않습니다.

## 동작 참고

GIF는 원본 애니메이션으로 표시합니다. MP4 목록은 재생 버튼으로 표시하고 클릭 시 동영상을 로드합니다. MP4 내부 코덱이 브라우저에서 지원되어야 재생됩니다. 이미지는 별도 축소 파일 없이 원본을 지연 로딩하므로 큰 이미지가 많으면 전송량이 늘어날 수 있습니다. 재귀 검색은 요청마다 다시 수행합니다.

## 검증

```bash
cd apps/photo_browser
.venv/bin/python -m unittest -v test_app.py
```

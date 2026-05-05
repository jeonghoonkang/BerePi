# PulseDAV

호스트 상태를 Markdown 파일로 만들고 WebDAV 서버로 전송하는 도구입니다.

## 수집 항목

- CPU 상태
- 내부 IP 주소
- Public IP 주소
- 내부 GW 주소
- DDNS 이름
- SSH 포트
- GPU 리스트
- GPU 스펙
- HDD 공간
- 서비스 중 사용자가 실행한 서비스
- `screen` 리스트
- `crontab`
- Docker 운영 상태

## 동작

- WebDAV 루트 디렉토리 하위에 `pulsedav` 디렉토리를 만들고, 그 아래에 자신의 호스트명 디렉토리를 만듭니다.
- 전송할 때마다 `pulse_YYYYMMDD_HHMMSS.md` 파일을 새로 만듭니다.
- 36개월보다 오래된 원격 파일은 자동 삭제합니다.
- 부팅 후 첫 전송 메세지에는 `부팅한 직후`를 포함합니다.
- 그 이후 전송 메세지에는 `up 이후 N분`을 포함합니다.

## 실행

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav
streamlit run app.py
```

수동 1회 전송:

```bash
python3 sender.py --once
```

초기 세팅 값 출력:

```bash
python3 sender.py --show-defaults
```

현재 세팅 확인:

```bash
python3 sender.py --show-settings
```

CLI에서 서버, 포트, root dir 등을 지정해 1회 전송:

```bash
python3 sender.py --once \
  --server keties.mooo.com \
  --port 22443 \
  --scheme https \
  --root-dir /remote.php/dav/files/tinyos \
  --username tinyos \
  --password 'your-password'
```

CLI에서 지정한 값을 `settings.json`에 저장:

```bash
python3 sender.py --show-settings \
  --server keties.mooo.com \
  --port 22443 \
  --root-dir /remote.php/dav/files/tinyos \
  --write-settings
```

반복 전송:

```bash
python3 sender.py --loop
```

## 부팅 자동 전송 예시

```cron
@reboot cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1
*/30 * * * * cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1
```

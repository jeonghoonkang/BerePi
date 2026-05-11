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

- WebDAV 루트 디렉토리 하위에 `tinyGW` 디렉토리를 만들고, 그 아래에 자신의 호스트명 디렉토리를 만듭니다.
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

설정 파일 경로를 직접 지정하려면:

```bash
python3 sender.py --once --config /path/to/custom-settings.json
```

반복 전송:

```bash
python3 sender.py --loop
```

반복 전송에서도 설정 파일 경로를 지정할 수 있습니다:

```bash
python3 sender.py --loop --config /path/to/custom-settings.json
```

crontab 에 넣을 예시 라인을 CLI 에서 바로 출력하려면:

```bash
python3 sender.py --print-crontab
python3 sender.py --print-crontab --config /path/to/custom-settings.json
```

## 설정 파일

- 기본 설정 파일은 `/Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav/settings.json` 입니다.
- CLI 에서 `--config` 를 주면 해당 JSON 파일을 설정 파일로 사용합니다.
- 지정한 설정 파일이 없으면 기본값 템플릿과 병합되어 동작합니다.
- `--print-crontab` 은 현재 설정 기준으로 `@reboot` 와 주기 실행 cron 라인을 출력합니다.
- `--config` 와 함께 쓰면 해당 설정 파일 경로가 포함된 cron 라인을 출력합니다.

## 부팅 자동 전송 예시

```cron
@reboot cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1
*/30 * * * * cd /Users/tinyos/devel_opment/BerePi/apps/tinyGW/pulsedav && /usr/bin/python3 sender.py --once >> pulsedav.log 2>&1
```

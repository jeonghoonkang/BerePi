# tinyGW Server List

hexagon 조각으로 위치를 나누고, 각 조각을 클릭해 서버 세부 리스트를 관리하는 Streamlit 앱입니다.

## 기능

- 첫 실행 시 사용할 hexagon 개수 등록
- hexagon 개수와 한 줄당 배치 개수 저장
- hexagon 조각 클릭 시 해당 위치의 서버 목록 표시
- 서버명, IP주소, Public IP, 포트번호, 상태, 메모 입력
- 서버 수정, 삭제, 다른 hexagon 위치로 이동
- GitHub의 `_server_list.json` 파일에 데이터 저장

## 실행

```bash
cd BerePi/apps/tinyGW/serverlist
pip install -r requirements.txt
cp config_key.conf.sample config_key.conf
vi config_key.conf
./run.sh
```

또는 직접 실행할 수 있습니다.

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 2298
```

포트나 바인딩 주소를 바꾸려면 환경변수를 사용합니다.

```bash
SERVERLIST_PORT=2300 SERVERLIST_HOST=127.0.0.1 ./run.sh
```

Windows에서 `streamlit` 명령이 PATH에 없으면 아래처럼 실행할 수 있습니다.

```bash
py -m streamlit run app.py --server.address 0.0.0.0 --server.port 2298
```

## 처음 실행

1. `Hexagon 개수`를 입력합니다.
2. `한 줄당 hexagon 개수`를 입력합니다.
3. `서버 리스트 시작`을 누르면 GitHub의 `_server_list.json`이 생성됩니다.

이후부터는 저장된 hexagon 구성을 기준으로 서버 리스트 관리 화면이 열립니다.

## 서버 이동

서버가 등록된 hexagon을 선택한 뒤 `서버 수정 및 이동` 영역에서 `이동할 hexagon 위치`를 변경하고 `수정/이동 저장`을 누르면 서버가 다른 조각으로 이동합니다.

## 데이터 파일

기본 저장 위치:

https://github.com/KETI-IISRC-AX/SW-Platform/blob/main/_server_list.json

GitHub에 저장하려면 `config_key.conf`에 쓰기 권한이 있는 토큰을 설정해야 합니다.

```conf
SERVERLIST_GITHUB_TOKEN=github_pat_...
```

토큰은 `SERVERLIST_GITHUB_TOKEN` 환경변수 또는 Streamlit secret으로도 설정할 수 있습니다.

기본 대상은 아래 환경변수로 변경할 수 있습니다.

```bash
SERVERLIST_GITHUB_OWNER=KETI-IISRC-AX
SERVERLIST_GITHUB_REPO=SW-Platform
SERVERLIST_GITHUB_BRANCH=main
SERVERLIST_GITHUB_PATH=_server_list.json
```

백업이 필요하면 앱 하단의 `_server_list.json 다운로드` 버튼을 사용하면 됩니다.

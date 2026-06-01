# tinyGW Server List

hexagon 조각으로 위치를 나누고, 각 조각을 클릭해 서버 세부 리스트를 관리하는 Streamlit 앱입니다.

## 기능

- 첫 실행 시 사용할 hexagon 개수 등록
- hexagon 개수와 한 줄당 배치 개수 저장
- hexagon 조각 클릭 시 해당 위치의 서버 목록 표시
- 서버명, IP주소, Public IP, 포트번호, 상태, 메모 입력
- 서버 수정, 삭제, 다른 hexagon 위치로 이동
- `servers.json` 파일에 데이터 저장

## 실행

```bash
cd BerePi/apps/tinyGW/serverlist
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 2298
```

Windows에서 `streamlit` 명령이 PATH에 없으면 아래처럼 실행할 수 있습니다.

```bash
py -m streamlit run app.py --server.address 0.0.0.0 --server.port 2298
```

## 처음 실행

1. `Hexagon 개수`를 입력합니다.
2. `한 줄당 hexagon 개수`를 입력합니다.
3. `서버 리스트 시작`을 누르면 `servers.json`이 생성됩니다.

이후부터는 저장된 hexagon 구성을 기준으로 서버 리스트 관리 화면이 열립니다.

## 서버 이동

서버가 등록된 hexagon을 선택한 뒤 `서버 수정 및 이동` 영역에서 `이동할 hexagon 위치`를 변경하고 `수정/이동 저장`을 누르면 서버가 다른 조각으로 이동합니다.

## 데이터 파일

기본 저장 위치:

```text
BerePi/apps/tinyGW/serverlist/servers.json
```

백업이 필요하면 앱 하단의 `servers.json 다운로드` 버튼을 사용하면 됩니다.

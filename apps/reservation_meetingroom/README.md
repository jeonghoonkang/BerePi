# 미팅룸 예약 (캘린더 + QR)

`apps/reservation_meetingroom` 는 Streamlit 기반의 회의실 예약 앱입니다.

## 기능

- 회의실(최대 10개) 이름 등록/수정
- 캘린더에서 드래그로 시간 구간 선택 → 예약 생성
- 이벤트 클릭 → 예약 수정/삭제
- 예약 상세를 QR 코드로 생성 (모바일에서 스캔)
- 로컬 SQLite(DB 파일)로 데이터 저장

## 실행 방법

### 1) 설치

```bash
cd E:\devel\BerePi\apps\reservation_meetingroom
pip install -r requirements.txt
```

### 2) 실행 (기본)

```bash
cd E:\devel\BerePi\apps\reservation_meetingroom
streamlit run app.py
```

### 3) 실행 (headless 옵션)

```bash
python3 -m streamlit run app.py --server.headless true
```

### 4) 실행 (휴대폰/다른 PC에서 접속 가능하게 열기)

같은 네트워크(예: 동일 Wi‑Fi)에서 휴대폰으로 접속하려면 `0.0.0.0`로 바인딩하세요.

```bash
python3 -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

## 사용 방법

### 회의실 등록 (최대 10개)

- 왼쪽 사이드바 **회의실 설정 (최대 10개)** 에서 회의실 이름을 줄바꿈으로 입력 후 저장합니다.

### 예약 생성

- 캘린더에서 시간 구간을 **드래그 선택**하면 선택 구간이 폼에 반영됩니다.
- 제목/회의실/시간을 확인하고 **저장**을 누르면 예약이 생성됩니다.

### 예약 수정/삭제

- 캘린더에서 이벤트를 **클릭**하면 해당 예약이 선택됩니다.
- 폼에서 값을 바꾸고 **저장**하면 수정됩니다.
- **삭제** 버튼으로 삭제할 수 있습니다.
- 캘린더에서 이벤트를 드래그/리사이즈로 시간 변경 시, 겹치지 않으면 DB에 저장됩니다.

## QR 코드(모바일 접속) 안내

- QR에는 기본적으로 “예약 요약 텍스트”가 들어갑니다.
- 만약 앱을 같은 Wi‑Fi에서 휴대폰으로 접속시키고 싶다면,
  - Streamlit 실행 시 `--server.address 0.0.0.0` 로 열고,
  - 사이드바의 **Base URL**을 예: `http://PC_IP:8501` 로 설정하면,
  - QR에 “URL + event_id” 형태 링크가 포함됩니다.

예:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### Base URL 아래 “현재 시스템 접속 주소” 표시

- 앱이 로컬에서 감지한 IP 중 **`10.x.x.x` 또는 `192.x.x.x` 대역이 있으면 우선 표시**합니다.
- 표시된 주소를 그대로 복사해서 Base URL에 넣으면 QR에 링크가 들어갑니다.


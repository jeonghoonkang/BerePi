# 미팅룸 예약 (캘린더 + QR)

`apps/reservation_meetingroom` 는 Streamlit 기반의 회의실 예약 앱입니다.

## 기능

- 회의실(최대 10개) 이름 등록/수정
- 캘린더에서 드래그로 시간 구간 선택 → 예약 생성
- 이벤트 클릭 → 예약 수정/삭제
- 예약 상세를 QR 코드로 생성 (모바일에서 스캔)
- 로컬 SQLite(DB 파일)로 데이터 저장

## 실행 방법 (Windows 예시)

```bash
cd E:\devel\BerePi\apps\reservation_meetingroom
pip install -r requirements.txt
streamlit run app.py
```

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


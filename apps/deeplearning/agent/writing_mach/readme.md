# Writing Mach

`story_backbone.md`를 기준으로 책 초안을 생성하는 로컬 웹 에이전트입니다.

<img width="1408" height="768" alt="image" src="https://github.com/user-attachments/assets/1e8821b5-b663-42b8-8264-fbebab3b71e8" />


## 흐름

1. `story_backbone.md`에서 제목과 챕터 구성을 읽습니다.
2. 챕터별 에이전트가 각 챕터 1차 초안을 작성합니다.
3. `main writer agent`가 모든 챕터 출력을 검토해 전체 방향, 반복, 누락, 초반부 수정 방향을 정리합니다.
4. lead writer가 챕터 에이전트 출력과 main writer 지시를 참고해 도입부와 1챕터 초반을 다시 작성합니다.
5. 최종 원고를 `output/book_YYYYMMDD_HHMMSS.md`로 저장합니다.

## 실행

```powershell
cd E:\devel\BerePi\apps\deeplearning\agent\writing_mach
py -3 .\client_service.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8786
```

포트 변경:

```powershell
$env:WRITING_MACH_PORT="8790"
py -3 .\client_service.py
```

## 모델 연결

좌측 **생성형 AI 연결** 패널에서 모델 서버 주소를 입력합니다.

- `Model URL`: 예: `http://127.0.0.1:8082`
- `Generate Path`: 기본값 `/api/generate`
- `Status Path`: 기본값 `/api/status`
- `User ID`, `Password`: 서버 인증 정보
- `Model Override`: 서버 기본 모델 대신 사용할 모델명
- `Chapter Words`: 챕터 에이전트가 목표로 하는 챕터별 분량

`연결 확인`으로 `/api/status`를 테스트하고, `설정 저장`으로 `data/client_config.json`에 저장합니다.

## 출력 파일

실행 결과는 `output` 폴더에 저장됩니다.

```text
output/book_YYYYMMDD_HHMMSS.md
output/run_YYYYMMDD_HHMMSS.json
```

`run_*.json`에는 각 챕터 에이전트 출력, main writer 조율 메모, 수정된 초반부가 함께 기록됩니다.

## CLI Progress Log

에이전트를 실행하면 `client_service.py`를 띄운 터미널에 컬러 진행 로그가 표시됩니다.

- `chapter`: 각 챕터 에이전트 초안 시작/완료
- `main-writer`: 전체 방향 조율 메모 작성
- `lead-writer`: 뒤 챕터 출력을 참고한 초반부 재작성
- `compile`, `save`, `done`: 최종 원고 조립 및 저장

색상 출력을 끄려면 아래 환경변수 중 하나를 설정합니다.

```powershell
$env:NO_COLOR="1"
# 또는
$env:WRITING_MACH_NO_COLOR="1"
```

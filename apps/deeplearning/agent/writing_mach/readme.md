# Writing Mach

`story_backbone.md`를 기준으로 책 초안을 생성하는 로컬 웹 에이전트입니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/1e8821b5-b663-42b8-8264-fbebab3b71e8" />


## 흐름

1. `story_backbone.md`에서 제목과 챕터 구성을 읽습니다.
2. 챕터별 파이프라인이 `outline → writer → reviewer → finalizer` 순서로 한 챕터를 처리합니다.
3. 서로 다른 챕터는 `Parallel Chapters` 설정에 따라 병렬 실행됩니다.
4. `main writer agent`가 모든 챕터 최종안을 모아 전체 방향, 반복, 누락, 초반부 수정 방향을 정리합니다.
5. lead writer가 챕터 에이전트 출력과 main writer 지시를 참고해 도입부와 1챕터 초반을 다시 작성합니다.
6. 최종 원고를 `output/book_YYYYMMDD_HHMMSS.md`로 저장합니다.

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
- `Parallel Chapters`: 동시에 처리할 챕터 수
- `Chapter Retry`: 챕터 파이프라인 실패 시 재시도 횟수
- `Pipeline Agents`: 실행할 챕터 단계. 기본값은 `outline,writer,reviewer,finalizer`
- `Global Review`: 모든 챕터 완료 후 main writer agent 리뷰 실행 여부
- `Allow Rewrite`: main writer agent가 챕터별 재작성 지시까지 내릴 수 있는지 여부
- `Agent Workers JSON`: 분산 실행에 사용할 모델 서버 목록

`연결 확인`으로 `/api/status`를 테스트하고, `설정 저장`으로 `data/client_config.json`에 저장합니다.

분산 worker 예시:

```json
[
  {
    "name": "gpu-1",
    "server_base_url": "http://10.0.0.11:8082",
    "max_parallel": 2
  },
  {
    "name": "gpu-2",
    "server_base_url": "http://10.0.0.12:8082",
    "max_parallel": 2
  }
]
```

챕터 내부의 단계는 항상 순차 실행됩니다. 예를 들어 한 챕터 안에서는 `outline` 결과를 `writer`가 보고, `writer` 결과를 `reviewer`가 보며, `reviewer` 결과를 `finalizer`가 정리합니다. 병렬화는 챕터 사이에서만 일어나므로 전체 흐름을 통제하기 쉽습니다.

전체 리뷰 에이전트는 모든 챕터 파이프라인이 끝난 뒤 한 번만 실행됩니다. `Global Review Focus`에 넣은 기준으로 원고 전체를 점검하고, `Allow Rewrite`가 꺼져 있으면 원고를 직접 다시 쓰지 않고 수정 지시만 생성합니다.

## 출력 파일

실행 결과는 `output` 폴더에 저장됩니다.

```text
output/book_YYYYMMDD_HHMMSS.md
output/run_YYYYMMDD_HHMMSS.json
```

`run_*.json`에는 각 챕터 에이전트 출력, main writer 조율 메모, 수정된 초반부가 함께 기록됩니다.

## CLI Progress Log

에이전트를 실행하면 `client_service.py`를 띄운 터미널에 컬러 진행 로그가 표시됩니다.

- `dispatch`: 병렬 실행 설정과 worker slot 정보
- `chapter`: 각 챕터 파이프라인 시작/완료
- `agent`: outline/writer/reviewer/finalizer 단계 시작/완료
- `main-writer`: 전체 방향 조율 메모 작성
- `lead-writer`: 뒤 챕터 출력을 참고한 초반부 재작성
- `compile`, `save`, `done`: 최종 원고 조립 및 저장

색상 출력을 끄려면 아래 환경변수 중 하나를 설정합니다.

```powershell
$env:NO_COLOR="1"
# 또는
$env:WRITING_MACH_NO_COLOR="1"
```

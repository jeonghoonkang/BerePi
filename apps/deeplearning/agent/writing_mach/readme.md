# Writing Mach

`story_backbone.md`를 기준으로 책 초안을 생성하는 로컬 웹 에이전트입니다.

<img width="800" alt="image" src="https://github.com/user-attachments/assets/1e8821b5-b663-42b8-8264-fbebab3b71e8" />


## 흐름

1. `story_backbone.md`에서 제목과 챕터 구성을 읽습니다.
2. 챕터별 파이프라인이 `outline → writer → reviewer → finalizer` 순서로 한 챕터를 처리합니다.
3. 서로 다른 챕터는 `Parallel Chapters` 설정에 따라 병렬 실행됩니다.
4. `main writer agent`가 모든 챕터 최종안을 모아 전체 방향, 반복, 누락, 초반부 수정 방향을 정리합니다.
5. lead writer가 챕터 에이전트 출력과 main writer 지시를 참고해 도입부와 1챕터 초반을 다시 작성합니다.
6. 최종 원고를 `output/book_YYYYMMDD_HHMMSS.md`와 `output/book_YYYYMMDD_HHMMSS.pdf`로 저장합니다.

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

시작 시 모델 서버 확인 타임아웃 변경:

```powershell
py -3 .\client_service.py --model-check-timeout 10
```

설정 파일 경로 지정:

```powershell
py -3 .\client_service.py --config .\data\my_client_config.json
```

웹 서버를 띄우지 않고 LLM 연결만 진단:

```powershell
py -3 .\client_service.py --config .\data\my_client_config.json --test
```

웹 버튼 클릭 없이 서비스 시작과 동시에 책 생성:

```powershell
py -3 .\client_service.py --config .\data\my_client_config.json --run-on-start
```

생성 완료 후 프로세스까지 종료:

```powershell
py -3 .\client_service.py --config .\data\my_client_config.json --run-on-start --exit-after-run
```

설정 파일에 저장하지 않고 LLM API 인증값 지정:

```powershell
py -3 .\client_service.py --llm-user <user_id> --llm-password <password>
```

서비스 시작 후 prompt 미전송 경고 시간 변경:

```powershell
py -3 .\client_service.py --prompt-warning-seconds 10
```

모델 서버가 살아 있지만 502/timeout이 반복될 때 재시도 대기 시간과 사용자 확인 기준 변경:

```powershell
py -3 .\client_service.py --model-retry-wait-seconds 30 --model-retry-prompt-after-failures 10
```

LLM 요청이 실패해 회신을 받지 못하면 같은 prompt를 바로 버리지 않고, 모델 서버의 `/api/status`에서 target/GPU/model queue 상태를 확인합니다. 비어 있는 target이 있으면 같은 prompt를 다시 전송하고, 모든 queue가 busy이면 `model_retry_wait_seconds` 단위로 다시 확인합니다.

deferred retry에서 model queue가 비어 있어 다른 prompt에 큰 영향을 주지 않는다고 판단되면 timeout을 2배, 이후 attempt에서는 최대 3배까지 늘려 실행합니다. 최대 배수는 `model_retry_max_timeout_multiplier`로 조정할 수 있습니다.

실행 중에는 checkpoint가 계속 저장됩니다. 중간 오류나 강제 종료 후 같은 backbone으로 다시 실행하면, 이미 완료된 챕터/agent 단계는 재실행하지 않고 저장된 산출물 다음 단계부터 이어서 실행합니다.

서비스 진행 로그 파일 경로 지정:

```powershell
py -3 .\client_service.py --log-file .\output\writing_mach_service.log
```

웹 로그인 계정 지정:

```powershell
py -3 .\client_service.py --web-user <user> --web-password <password>
```

`--web-user`, `--web-password`를 지정하지 않으면 서비스 시작 중 터미널에서 입력을 요청합니다.

## 시작 전 작성 파일

작업을 시작하려면 아래 파일을 준비합니다.

| 파일 | 필수 | 용도 |
| --- | --- | --- |
| `story_backbone.md` | 예 | 책 제목, 챕터 구성, 작성 방향을 적는 원본 기획서 |
| `data/client_config.json` | 예 | 모델 서버 연결, 병렬 실행, 리뷰 에이전트 제어 설정 |
| `config/client_config.sample.json` | 아니오 | 새 설정 파일을 만들 때 참고하는 샘플 |

`data/client_config.json`이 없으면 서비스 시작 시 `config/client_config.sample.json`을 기준으로 자동 생성됩니다. 생성 후 웹 화면에서 수정하거나 파일을 직접 편집하면 됩니다.

`story_backbone.md` 작성 예:

```markdown
- 제목은 Rock 음악의 역사와 주목할만한 앨범

  - 1 챕터
    - 1960년대, 1970년대 대중음악의 발전 변화
    - 주요 음악가 및 레코딩 리스트
    - 블루스, 포크, 사이키델릭 록이 대중음악에 준 영향

  - 2 챕터
    - 70년대 이후 Rock 음악의 장르별 주요 뮤지션
    - 국가별 진지한 대중음악 작업 리스트
    - 대표 음악, 영향력이 큰 앨범과 공연

  - 3 챕터
    - 대중음악의 흐름을 바꾼 레코드와 뮤지션
    - 프로듀싱, 녹음 기술, 앨범 단위 감상의 변화

- 작성방법
  - 각 챕터는 독립적인 글이면서 전체 책의 흐름에 연결되도록 작성
  - 독자 대상은 음악사를 처음 공부하는 일반 독자
  - main writer agent는 챕터 간 반복, 용어 통일, 시대 흐름을 중점 검토
```

`data/client_config.json` 단일 서버 작성 예:

```json
{
  "server_base_url": "http://127.0.0.1:8082",
  "generate_path": "/api/generate",
  "status_path": "/api/status",
  "request_timeout_seconds": 600,
  "user_id": "id",
  "password": "pass",
  "model": "",
  "keep_alive": "6m",
  "num_ctx": 8192,
  "target_words_per_chapter": 1800,
  "language": "ko",
  "chapter_parallelism": 1,
  "chapter_retry": 2,
  "model_retry_wait_seconds": 30,
  "model_retry_prompt_after_failures": 10,
  "model_retry_status_timeout_seconds": 10,
  "model_retry_max_timeout_multiplier": 3,
  "pipeline_agents": ["outline", "writer", "reviewer", "finalizer"],
  "agent_workers": [],
  "global_review_enabled": true,
  "global_review_mode": "strict",
  "global_review_focus": [
    "전체 논지 일관성",
    "챕터 간 반복 제거",
    "용어 통일",
    "시대 흐름 점검",
    "도입부와 결론의 연결"
  ],
  "allow_global_rewrite": false
}
```

분산 worker를 사용할 때의 `data/client_config.json` 작성 예:

```json
{
  "server_base_url": "http://127.0.0.1:8082",
  "generate_path": "/api/generate",
  "status_path": "/api/status",
  "request_timeout_seconds": 900,
  "user_id": "id",
  "password": "pass",
  "model": "",
  "keep_alive": "6m",
  "num_ctx": 8192,
  "target_words_per_chapter": 1800,
  "language": "ko",
  "chapter_parallelism": 4,
  "chapter_retry": 2,
  "model_retry_wait_seconds": 30,
  "model_retry_prompt_after_failures": 10,
  "model_retry_status_timeout_seconds": 10,
  "model_retry_max_timeout_multiplier": 3,
  "pipeline_agents": ["outline", "writer", "reviewer", "finalizer"],
  "agent_workers": [
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
  ],
  "global_review_enabled": true,
  "global_review_mode": "strict",
  "global_review_focus": [
    "전체 논지 일관성",
    "챕터 간 반복 제거",
    "용어 통일",
    "시대 흐름 점검",
    "도입부와 결론의 연결"
  ],
  "allow_global_rewrite": false
}
```

`chapter_parallelism`은 동시에 실행할 챕터 수입니다. `agent_workers[].max_parallel`의 합보다 크게 설정해도 실제 병렬 실행 수는 worker slot 수를 넘지 않습니다.

`story_backbone.md`에 병렬 실행을 직접 명시할 수도 있습니다. 이 값은 실행 시 `data/client_config.json`보다 우선 적용되며, 시작 로그에 `parallel-alert`가 출력됩니다.

```markdown
- 작성방법
  - 병렬실행: true
  - 병렬 챕터: 3
```

여러 모델 worker를 backbone에 직접 지정할 때는 다음 형식을 사용할 수 있습니다.

```markdown
- 실행옵션
  - 병렬실행: true
  - 병렬 챕터: 4
  - 모델 worker: name=gpu-1, url=http://10.0.0.11:8082, model=gemma4:31b, max_parallel=2
  - 모델 worker: name=gpu-2, url=http://10.0.0.12:8082, model=qwen2.5:32b, max_parallel=2
```

챕터 내부의 `outline -> writer -> reviewer -> finalizer` 단계는 순서를 지키고, 서로 다른 챕터가 worker slot에 분산되어 병렬 실행됩니다.

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

중간 단계에서 실패해 deferred retry로 넘어가면 이미 완료된 앞 단계 산출물을 재사용합니다. 예를 들어 `finalizer`에서 실패한 챕터는 `outline`, `writer`, `reviewer`를 다시 실행하지 않고 `finalizer`부터 재개합니다. 선행 산출물이 없는 단계는 실행하지 않고 필요한 앞 단계부터 다시 진행합니다.

전체 리뷰 에이전트는 모든 챕터 파이프라인이 끝난 뒤 한 번만 실행됩니다. `Global Review Focus`에 넣은 기준으로 원고 전체를 점검하고, `Allow Rewrite`가 꺼져 있으면 원고를 직접 다시 쓰지 않고 수정 지시만 생성합니다.

## 출력 파일

실행 결과는 `output` 폴더에 저장됩니다.

```text
output/service_YYYYMMDD_HHMMSS.log
output/book_YYYYMMDD_HHMMSS_<elapsed>min.md
output/book_YYYYMMDD_HHMMSS_<elapsed>min.pdf
output/run_YYYYMMDD_HHMMSS_<elapsed>min.json
output/llm_trace_YYYYMMDD_HHMMSS/
output/checkpoints/checkpoint_<backbone_hash>.json
```

`service_*.log`에는 서버 시작, 접속 대기, API 요청, LLM 요청/응답 preview, 오류가 콘솔 출력과 함께 기록됩니다.

`run_*.json`에는 각 챕터 에이전트 출력, main writer 조율 메모, 수정된 초반부, PDF 생성 경로 또는 실패 사유가 함께 기록됩니다.

`llm_trace_*` 폴더에는 각 LLM 호출의 전체 prompt, 전체 response, 요청 URL, worker/model, 소요 시간, 실패 에러가 순번 JSON 파일로 저장됩니다.

`checkpoints` 폴더에는 실행 중 챕터별 `outline`, `draft`, `review`, `final`, main writer 메모, lead writer 수정본이 단계별로 저장됩니다. 오류로 종료된 실행은 다음 실행에서 이 파일을 읽어 이어서 진행합니다.

PDF 생성은 `pandoc`이 있으면 우선 사용하고, 없으면 Python `weasyprint`, 마지막으로 macOS `cupsfilter`를 시도합니다. Markdown을 그대로 PDF로 넘기지 않고 `book_*.pdf_source.html`을 먼저 만든 뒤 렌더링하므로 `#`, `>`, 표 구분자 같은 Markdown 기호가 그대로 출력되는 문제를 피합니다. 변환기가 없거나 실패하면 Markdown/JSON/HTML은 정상 저장하고 PDF 실패 사유를 로그에 남깁니다.

## CLI Progress Log

에이전트를 실행하면 `client_service.py`를 띄운 터미널에 컬러 진행 로그가 표시됩니다.

LLM 요청 로그에는 prompt 단어 수, 요청 timeout, 전송 후 응답까지 걸린 시간, 전체 누적 시간이 함께 표시됩니다. 실패나 timeout이 발생해도 동일한 형식으로 attempt별 소요 시간이 기록됩니다.

챕터 병렬 실행 중에는 30초마다 현재 실행 중인 챕터 worker 수가 `running N/M chapter worker(s)` 형식으로 출력됩니다.

챕터별 queue 상태도 `chapter-queue` 로그로 함께 출력됩니다. 각 챕터는 `pending`, `queued`, `running`, `finishing`, `completed`, `deferred`, `skipped`, `failed` 중 하나로 표시되며, 같은 내용은 `service_*.log`, `run_*.json`의 `chapter_queue`/`chapter_queue_history`, checkpoint 파일에도 저장됩니다.

- `model-check`: 서비스 시작 시 LLM `/api/status` 연결 확인. 응답이 없으면 즉시 경고를 출력합니다.
- `model-request`: LLM 요청 URL, 사용자, 모델, 컨텍스트 설정, 프롬프트 preview
- `model-response`: LLM 회신 단어 수와 응답 preview
- `service`: 서비스 시작 후 지정 시간 안에 LLM prompt가 전송되지 않으면 접속/실행 안내 출력
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

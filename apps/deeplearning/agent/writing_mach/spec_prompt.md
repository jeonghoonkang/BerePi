# Writing Mach Prompt Flow

## Overview

`client_service.py`는 사용자 입력 `backbone`을 책 기획서로 보고, 이를 챕터별 파이프라인 프롬프트로 변환한다.

기본 실행 흐름은 다음과 같다.

```text
backbone 입력
 -> 제목 추출
 -> 챕터 목록 파싱
 -> outline
 -> writer
 -> reviewer
 -> finalizer
 -> main-writer 전체 조율
 -> lead-writer 도입부 보정
 -> book_*.md / PDF 생성
```

## Backbone Input

관련 코드:

- [`read_story_backbone()`](./client_service.py#L755)
- [`title_from_backbone()`](./client_service.py#L1535)
- [`parse_chapters()`](./client_service.py#L761)
- [`parse_backbone_runtime_options()`](./client_service.py#L824)

`backbone`은 `--backbone` 옵션 파일, 기본 `story_backbone.md`, 또는 웹/API 입력으로 전달된다.

예시:

```md
- 제목은 동형 암호화 기술 소개와 기업용 제조 데이터 시스템 응용

  - 1 챕터
    - 동형 암호화 개념
    - 기존 AES와 차이점

  - 2 챕터
    - 딥러닝 모델 보안
    - 동형 암호 기반 모델 교환
```

제목은 다음 순서로 결정된다.

1. `제목은 ...`
2. 첫 번째 Markdown `# ...`
3. 기본값 `untitled-book`

챕터는 `- 1 챕터`, `- 2 챕터` 형식으로 파싱된다. 각 챕터 아래 bullet은 해당 챕터의 상세 작성 지시로 사용된다.

## Shared Chapter Context

관련 코드:

- [`book_brief()`](./client_service.py#L1545)
- [`chapter_source_section()`](./client_service.py#L1553)
- [`chapter_context()`](./client_service.py#L1581)

`outline`, `writer`, `reviewer`, `finalizer`는 모두 공통으로 아래 정보를 받는다.

```text
책 전체 개요
담당 챕터 상세 기획
공통 작성 지침
```

공통 작성 지침에는 한국어 작성, 목표 분량, 사실 설명과 기술 맥락, 독립된 챕터 제목과 절 구성, 메타 설명 제거 등이 포함된다.

## Outline Agent

관련 코드:

- [`outline_prompt()`](./client_service.py#L1597)

역할은 챕터 구조 설계이다.

입력:

```text
backbone 전체 개요
+ 현재 챕터 bullet
+ 공통 작성 지침
```

주요 작업:

1. 챕터 도입부 hook 제안
2. 3~6개 주요 절 설계
3. 각 절의 핵심 논점, 사례, 연결 문장 정리
4. 다른 챕터와 연결될 전환 메모 작성

출력 예:

```md
# 1 챕터 Outline
## 도입
...
## 절 구성
...
## 전환 메모
...
```

출력은 `outline`으로 저장된다.

## Writer Agent

관련 코드:

- [`writer_prompt()`](./client_service.py#L1619)

역할은 챕터 초안 작성이다.

입력 변화:

```text
backbone 전체 개요
+ 현재 챕터 bullet
+ 공통 작성 지침
+ outline agent 산출물
```

주요 작업:

- outline 구조를 따라 초안 작성
- bullet 위주로 2~3줄 분량 작성
- Markdown heading으로 시작
- reviewer와 finalizer가 보기 전 단계이므로 내용 누락 없이 충분히 작성

출력은 `draft`로 저장된다.

## Reviewer Agent

관련 코드:

- [`reviewer_prompt()`](./client_service.py#L1635)

역할은 writer 초안 개선이다.

입력 변화:

```text
backbone 전체 개요
+ 현재 챕터 bullet
+ 공통 작성 지침
+ outline
+ writer 초안
```

주요 작업:

1. 명확성, 흐름, 완성도, 용어 일관성, 흥미도 기준으로 초안 개선
2. outline에서 빠진 내용 보강
3. 어색하거나 과장된 사실관계를 보수적으로 정리

출력은 리뷰 코멘트가 아니라 개선된 챕터 전체 원고이며, `review`로 저장된다.

## Finalizer Agent

관련 코드:

- [`finalizer_prompt()`](./client_service.py#L1662)

역할은 최종 챕터 원고 정리이다.

입력 변화:

```text
backbone 전체 개요
+ 현재 챕터 bullet
+ 공통 작성 지침
+ reviewer 개선 원고
```

주요 작업:

- Markdown heading 계층 정리
- 반복, TODO, 메타 코멘트, 불필요한 안내문 제거
- 문단 사이 전환을 부드럽게 다듬기
- 챕터 제목으로 시작하는 최종 원고만 출력

출력은 `final`로 저장된다.

## Prompt Accumulation

단계가 진행될수록 프롬프트는 다음처럼 누적된다.

```text
outline:
backbone + 현재 챕터 지시

writer:
backbone + 현재 챕터 지시 + outline 결과

reviewer:
backbone + 현재 챕터 지시 + outline 결과 + writer 초안

finalizer:
backbone + 현재 챕터 지시 + reviewer 개선 원고
```

## Execution Pipeline

관련 코드:

- [`run_chapter_pipeline()`](./client_service.py#L2297)
- [`run_book_agents()`](./client_service.py#L2680)

`run_chapter_pipeline()`은 각 챕터에 대해 다음 순서로 모델을 호출한다.

```text
outline -> writer -> reviewer -> finalizer
```

예를 들어 챕터가 3개이면 기본 LLM 호출 횟수는 다음과 같다.

```text
챕터 1: outline -> writer -> reviewer -> finalizer = 4회
챕터 2: outline -> writer -> reviewer -> finalizer = 4회
챕터 3: outline -> writer -> reviewer -> finalizer = 4회
전체: main-writer 조율 = 1회
전체: lead-writer 도입부 보정 = 1회
총 약 14회
```

각 단계 결과는 checkpoint에 저장된다. 실패하면 완료된 단계 결과를 유지하고, 재시도 시 가능한 단계부터 이어서 실행한다.

모든 챕터가 끝나면 `run_book_agents()`가 다음 후처리를 수행한다.

1. `main-writer`가 전체 챕터 결과를 보고 조율 메모 작성
2. `lead-writer`가 도입부와 초반부를 다시 정리
3. `compile_book()`이 최종 Markdown 구성
4. `write_book_pdf()`가 PDF 생성을 시도

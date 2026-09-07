# Agent Skills 지원 스킬 명세

## 문서 목적

이 문서는 [Agent Skills 공식 사이트](https://agentskills.io/home)의 규격과 이 사이트가 공식 예제로 연결하는 [Anthropic Skills 저장소](https://github.com/anthropics/skills)를 기준으로, 공개된 예제 스킬의 이름, 파일 위치, 기능을 한글로 정리한다.

> 참고: Agent Skills는 정해진 스킬 목록을 제공하는 제품이 아니라, 에이전트 기능을 확장하기 위한 개방형 파일 규격이다. 아래 목록은 규격 자체가 반드시 지원해야 한다고 정한 내장 스킬이 아니라, 공식 사이트에서 연결하는 예제 저장소의 스킬 목록이다. 확인 기준일은 2026-09-06이다.

## 기본 파일 구조

모든 스킬은 스킬 이름과 같은 디렉터리 아래에 `SKILL.md`를 필수로 둔다.

```text
skill-name/
├── SKILL.md       # 필수: 이름, 설명 등의 메타데이터와 실행 지침
├── scripts/       # 선택: 실행 가능한 Python, Bash, JavaScript 등의 코드
├── references/    # 선택: 상세 문서와 참고 자료
└── assets/        # 선택: 템플릿, 이미지, 데이터 등의 정적 자원
```

`SKILL.md`의 YAML frontmatter에는 최소한 `name`과 `description`이 있어야 한다. `name`은 부모 디렉터리 이름과 같아야 하며, 소문자 영문자·숫자·하이픈만 사용할 수 있다.

## 공개 예제 스킬 목록

기준 저장소 루트: `https://github.com/anthropics/skills/tree/main/skills`

| 스킬 이름 | 파일 위치 | 기능 |
|---|---|---|
| `academy-guide` | `skills/academy-guide/SKILL.md` | Claude 및 Claude 제품 사용법을 묻는 사용자에게 Claude Academy의 관련 과정, 튜토리얼, 활용 사례를 안내한다. |
| `algorithmic-art` | `skills/algorithmic-art/SKILL.md` | 시드 기반 난수와 p5.js를 사용해 플로 필드, 입자 시스템 등의 독창적인 생성형·알고리즘 아트를 제작한다. |
| `brand-guidelines` | `skills/brand-guidelines/SKILL.md` | 문서와 시각 결과물에 Anthropic의 공식 색상, 타이포그래피, 브랜드 스타일을 적용한다. |
| `canvas-design` | `skills/canvas-design/SKILL.md` | 포스터, 아트워크 등 정적인 시각 디자인을 독창적으로 설계하고 PNG 또는 PDF로 제작한다. |
| `claude-api` | `skills/claude-api/SKILL.md` | Claude API와 Anthropic SDK의 모델, 가격, 파라미터, 스트리밍, 도구 사용, MCP, 캐싱, 토큰 계산 및 마이그레이션 정보를 제공한다. |
| `discernment-nudge` | `skills/discernment-nudge/SKILL.md` | 사용자가 중요한 답변이나 초안을 실제 행동에 옮기기 전에 핵심 사실, 가정, 누락된 맥락을 점검하도록 후속 질문을 제안한다. |
| `doc-coauthoring` | `skills/doc-coauthoring/SKILL.md` | 문서, 제안서, 기술 명세, 의사결정 문서 등을 공동 작성할 때 맥락 수집, 구조화·개선, 독자 검증의 단계별 흐름을 안내한다. |
| `docx` | `skills/docx/SKILL.md` | Word 문서와 템플릿(`.docx`, `.dotx`)을 생성, 읽기, 편집, 서식 지정, 변환 및 검증한다. |
| `frontend-design` | `skills/frontend-design/SKILL.md` | 새 UI를 만들거나 기존 UI를 개편할 때 주제에 맞는 미적 방향, 타이포그래피, 색상, 레이아웃을 설계한다. |
| `internal-comms` | `skills/internal-comms/SKILL.md` | 상태 보고, 리더십 업데이트, 사내 뉴스레터, FAQ, 장애 보고서, 프로젝트 업데이트 등 사내 커뮤니케이션 문서를 작성한다. |
| `mcp-builder` | `skills/mcp-builder/SKILL.md` | Python FastMCP 또는 Node/TypeScript MCP SDK로 외부 API·서비스와 연동되는 고품질 MCP 서버를 설계하고 구현한다. |
| `pdf` | `skills/pdf/SKILL.md` | PDF 읽기·생성, 텍스트와 표 추출, 병합·분할·회전, 워터마크, 양식 입력, 암호화, 이미지 추출 및 OCR을 수행한다. |
| `pptx` | `skills/pptx/SKILL.md` | PowerPoint 파일과 템플릿(`.pptx`, `.potx`)을 생성, 읽기, 편집, 병합·분할하고 레이아웃, 발표자 노트, 댓글을 처리한다. |
| `skill-creator` | `skills/skill-creator/SKILL.md` | 새 스킬을 만들거나 기존 스킬을 수정·최적화하고, 평가와 벤치마크를 통해 성능 및 호출 정확도를 개선한다. |
| `slack-gif-creator` | `skills/slack-gif-creator/SKILL.md` | Slack 이모지와 메시지에 적합한 크기 및 제약 조건을 지키는 애니메이션 GIF를 제작하고 검증한다. |
| `theme-factory` | `skills/theme-factory/SKILL.md` | 슬라이드, 문서, 보고서, HTML 랜딩 페이지 등에 미리 정의된 색상·글꼴 테마를 적용하거나 새 테마를 생성한다. |
| `web-artifacts-builder` | `skills/web-artifacts-builder/SKILL.md` | React, Tailwind CSS, shadcn/ui를 사용해 상태 관리와 라우팅을 포함하는 복합 HTML 웹 아티팩트를 구축한다. |
| `webapp-testing` | `skills/webapp-testing/SKILL.md` | Playwright를 이용해 로컬 웹 애플리케이션의 기능과 UI 동작을 테스트하고, 브라우저 로그 및 화면 캡처를 확인한다. |
| `xlsx` | `skills/xlsx/SKILL.md` | Excel 및 표 형식 파일(`.xlsx`, `.xlsm`, `.xltx`, `.csv`, `.tsv`)을 생성, 읽기, 편집, 정리, 계산, 차트 작성 및 변환한다. |

## 엑셀 데이터 처리 및 그래프 작성에 적합한 스킬

요구 기능에 가장 직접적으로 대응하는 공식 예제는 `xlsx` 스킬이다.

| 항목 | 내용 |
|---|---|
| 스킬 이름 | `xlsx` |
| 파일 위치 | `skills/xlsx/SKILL.md` |
| 지원 입력 파일 | `.xlsx`, `.xlsm`, `.xltx`, `.csv`, `.tsv` |
| 지원 출력 파일 | 처리 결과, 수식, 서식, 표, 차트를 포함하는 Excel 파일 |
| 주요 기능 | 엑셀 파일 읽기, 데이터 정제·변환·집계, 열 추가, 수식 계산, 결과 저장, 표 서식 지정, 차트 생성, 표 형식 간 변환 |
| 주요 도구 | `openpyxl`, `pandas`, `markitdown`, LibreOffice |

### 기능별 처리 방법

1. **엑셀 파일 읽기**
   - `pandas.read_excel()`로 시트의 대량 데이터를 읽는다.
   - `openpyxl.load_workbook()`으로 셀, 수식, 서식, 시트 구조를 읽는다.
   - 수식과 계산 결과가 모두 필요하면 일반 모드와 `data_only=True` 모드로 각각 읽는다.
2. **데이터 처리**
   - `pandas`로 결측값 처리, 필터링, 정렬, 중복 제거, 그룹 집계, 열 계산 등의 데이터 처리를 수행한다.
   - 결과가 입력값 변경에 따라 다시 계산되어야 하면 하드코딩한 값 대신 Excel 수식을 사용한다.
3. **처리 결과 저장**
   - `pandas.DataFrame.to_excel()`로 대량 처리 결과를 새 시트나 새 파일에 저장한다.
   - `openpyxl`로 기존 통합 문서에 결과를 기록하고 셀 서식, 수식, 표 구조를 유지하거나 추가한다.
   - 매크로 포함 파일(`.xlsm`)은 매크로 보존을 위해 `keep_vba=True`로 연다.
4. **그래프 작성**
   - `openpyxl.chart`를 이용해 막대, 선, 원형, 영역, 분산형 등의 Excel 차트를 결과 시트에 추가한다.
   - 차트의 데이터 범위, 제목, 축 이름, 범례, 크기와 위치를 명시하여 결과 통합 문서에 저장한다.
5. **결과 검증**
   - 수식이 포함된 파일은 LibreOffice로 재계산한 후 수식 오류가 없는지 검사한다.
   - 저장된 파일을 다시 열어 시트 이름, 행·열 수, 핵심 계산값, 수식, 차트 존재 여부를 확인한다.

### 권장 작업 흐름

```text
엑셀/CSV 입력
    ↓
pandas 또는 openpyxl로 데이터 읽기
    ↓
정제 · 변환 · 계산 · 집계
    ↓
결과 시트 작성 및 Excel 차트 생성
    ↓
Excel 파일로 저장
    ↓
수식 재계산 및 결과 검증
```

`xlsx` 스킬은 최종 산출물이 엑셀 파일일 때 사용한다. 최종 산출물이 Word 문서, HTML 보고서, 독립 실행형 Python 프로그램, 데이터베이스 파이프라인 또는 Google Sheets API 연동인 경우에는 이 스킬의 직접 적용 대상이 아니다.

## 규격에서 지원하는 주요 파일 위치와 역할

| 이름 | 파일 위치 | 기능 |
|---|---|---|
| 스킬 정의 | `<skill-name>/SKILL.md` | 필수 메타데이터와 에이전트가 따라야 할 작업 지침을 저장한다. |
| 실행 스크립트 | `<skill-name>/scripts/` | 반복적이거나 결정적인 처리를 수행하는 실행 코드를 저장한다. |
| 참고 문서 | `<skill-name>/references/` | 필요할 때만 읽을 상세 기술 문서, 양식, 분야별 지식을 저장한다. |
| 정적 자원 | `<skill-name>/assets/` | 문서 템플릿, 이미지, 스키마, 조회 테이블 등의 자원을 저장한다. |

## 출처

- [Agent Skills 개요](https://agentskills.io/home)
- [Agent Skills 규격](https://agentskills.io/specification)
- [공식 사이트에서 연결하는 Example Skills 저장소](https://github.com/anthropics/skills/tree/main/skills)
- [`xlsx` 스킬 원문](https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md)

# ZeroNative Streamlit App for RTX 5090

This ZeroNative-branded app runs a Streamlit UI on port `2280` and sends prompts to a local
Ollama server using the `gemma3:4b` model by default. It can also use
`qwen3:32b` as a larger general-purpose Qwen model, plus
`qwen3.5:9b`, `qwen2.5-coder:7b`, and `qwen3-coder:30b` for tool-capable or coding-oriented prompts and
tool calling. Workspace tools are enabled only for supported Qwen coder models.

## Features

- Text chat with `gemma3:4b`
- Optional Qwen model support with `qwen3:32b`, `qwen3.5:9b`, `qwen2.5-coder:7b`, and `qwen3-coder:30b`
- Excel upload support for `.xlsx` and `.xls`
- Image upload support for `.png`, `.jpg`, `.jpeg`, `.webp`, and `.bmp`
- External access with Streamlit bound to `0.0.0.0:2280`
- Sidebar model selection, installed model refresh, and model download
- Per-model temperature control from the Streamlit sidebar
- Auto-select the downloaded model as the active default
- GPU memory-based recommended model guidance when `nvidia-smi` is available
- Response elapsed time display after each prompt
- Current model information, local storage path, and model size display in the sidebar
- Uploaded Excel files are saved into the app-local `workspace` directory
- Files in the server `workspace` can be downloaded to the browser client from the landing page
- Files in the server `workspace` can also be deleted from the landing page with a confirmation button
- A right-side WebDAV / RAG panel can connect to Nextcloud WebDAV and read up to four configured paths
- Markdown and PDF files from WebDAV can be indexed into prompt-time RAG context
- Qwen can use validated workspace tools to list, read, write, copy, and delete files
- Qwen can prepare workspace files for direct download through the Streamlit UI
- User-selectable Ollama model storage path with model file migration support
- Remember the selected model storage path across Streamlit restarts
- Qwen can use Excel tools for workbook info, sheet preview, cell read/write, range aggregation, workbook merge, and vertical stacking into one sheet
- Qwen can calculate dataframe-style Excel statistics with optional filters, target columns, and grouped summaries
- Gemma can also use app-side Excel statistics helpers based on prompt parsing

## Assumption

`gemma model 4` is implemented as the Ollama model `gemma3:4b`, which is the
current practical Gemma 4B-style multimodal target for text and image inputs.

## Install

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Prepare Ollama

Start the Ollama server:

```bash
ollama serve
```

Download the model:

```bash
ollama pull gemma3:4b
```

You can also download a larger model directly from the Streamlit sidebar.

For coding and file-tool prompts, you can also download:

```bash
ollama pull qwen3:32b
ollama pull qwen3.5:9b
ollama pull qwen2.5-coder:7b
ollama pull qwen3-coder:30b
```

## Run

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
chmod +x run.sh
./run.sh
```

Or run directly:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 2280
```

## Notes

- The Streamlit port is fixed to `2280` by default in `.streamlit/config.toml`.
- If Ollama is not on the local host, set `OLLAMA_HOST`.
- If you want a different model tag, set `OLLAMA_MODEL`.
- Each model can keep its own temperature setting from `0.0` to `2.0`.
- Excel files are summarized into prompt context rather than being passed as raw binary.
- Uploaded Excel files are also saved into `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/workspace`.
- Files generated in `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/workspace` can be sent to the browser with the `Workspace Files` download section.
- The same `Workspace Files` section also supports browser-side delete actions with a second-click confirmation step.
- The right-side `WebDAV / RAG` panel is intended for Nextcloud WebDAV URLs such as `https://host/remote.php/dav/files/<user>/`.
- Up to four WebDAV read paths can be configured, and the app recursively loads `.md`, `.markdown`, and `.pdf` files from those paths into a lightweight lexical RAG index.
- Subdir inputs are relative to the configured WebDAV Base URL. For example, if the base URL is `/remote.php/dav/files/tinyos/`, entering `메모` reads `/remote.php/dav/files/tinyos/메모`.
- WebDAV settings are saved in `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/app_settings.json`.
- Excel tool calls support workbook inspection, sheet preview, cell reads/writes, numeric range operations such as `sum`, `average`, `min`, `max`, and `count`, plus multi-file merge in `append_rows` or `separate_sheets` mode, and single-sheet vertical stacking with configurable blank row gaps.
- The sidebar can refresh installed models via `GET /api/tags` and download models via `POST /api/pull`.
- The app tries to detect GPU memory using `nvidia-smi` and recommends a model size accordingly.
- The inferred storage path follows the local `OLLAMA_MODELS` setting or the default `~/.ollama/models` path.
- Workspace file tools are limited to the app-local `workspace` directory for safety.
- Qwen coder models run with workspace tool calling, while Gemma models stay in normal chat mode without workspace tool calling.
- The same WebDAV RAG context is shared across the selectable Gemma and Qwen models; only tool-calling capability differs by model family.
- When a user asks to download a workspace file, the tool-capable model can call `download_file` and the app shows a button in the `Workspace Downloads` section.
- If a tool-capable model repeats the same tool call or reaches the tool round cap, the app now asks the model for a final non-tool answer instead of failing immediately.
- Changing the model storage path in the app updates the desired location and can move existing files, but Ollama must be restarted with `OLLAMA_MODELS` set to the same path for future downloads to use it.
- The selected model storage path is saved in `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/app_settings.json` and restored on the next app start.

## Tool Calling

This app has two different prompt-handling paths.

- `qwen2.5-coder:7b`, `qwen3-coder:30b`, and `qwen3.5:9b` use Ollama tool calling for validated workspace and Excel tools.
- `qwen3:32b` can be selected as a larger general-purpose Qwen chat model, but it does not enable workspace tool calling in this app.
- `gemma3:*` models do not use Ollama workspace tool calling in this app. Instead, the Streamlit app pre-processes some prompt patterns and injects the matched file content into the model prompt.

### Qwen Tool Calling

When a supported Qwen coder model is selected, the app may expose tools such as:

- `list_files`
- `read_file`
- `write_file`
- `copy_path`
- `delete_path`
- `download_file`
- `excel_workbook_info`
- `excel_sheet_preview`
- `excel_read_cells`
- `excel_write_cell`
- `excel_aggregate_range`
- `excel_calculate_statistics`
- `excel_merge_files`
- `excel_stack_files_to_single_sheet`

These tools are limited to the app-local `workspace` directory for safety.

### Gemma Prompt Helpers

When a Gemma model is selected, the app still supports file-assisted prompts through prompt parsing. The UI shows `workspace 스캔 중...` while this helper path runs.

Current prompt patterns:

- `작업파일 <file>`:
  The app looks for the file that appears immediately after `작업파일`, resolves it inside `workspace`, opens it with Python `open(..., encoding="utf-8", errors="replace")`, and injects the content into the model prompt.
- `작업파일: <file>` or `작업파일 "<file>"`:
  The same task-file flow also supports `:` and quoted file names.
- `<filename>.txt`, `<filename>.md`, `<filename>.json`, and similar file names written directly in the prompt:
  The app searches the `workspace` for matching relative paths, basenames, and stem names, then prioritizes those files during prompt-time workspace scanning.
- Korean and English file-reading prompts such as `파일 내용 알려줘`, `파일 읽어`, `read file`, `find file`, `check file`:
  The app scans text-like files in `workspace` and injects the most relevant file excerpts into the prompt.

If the requested file is not found, the app shows a warning in the UI and tells the model that the file was not found in `workspace`.

### Example Prompts

```text
작업파일 notes/todo.md 읽어서 알려줘
작업파일: README
작업파일 "report.txt" 내용 정리해줘
config.json 파일 내용 보고 설명해줘
workspace 에서 memo.md 찾아서 알려줘
```

### Ask for Available Tools

You can also ask the app to list the currently available tools directly from the prompt.

- `사용가능한 tool 알려줘`
- `tool 목록 알려줘`
- `available tools`

Behavior:

- When `qwen2.5-coder:7b` or `qwen3-coder:30b` is selected, the app returns the registered Ollama tool list with each tool name and description.
- When a `gemma3:*` model is selected, the app explains that Ollama tool calling is disabled for Gemma in this app and shows the available app-side helper flows such as `작업파일 <file>` and workspace scan prompts.

### Excel Statistics Tool

Supported Qwen coder models can use `excel_calculate_statistics` directly, and Gemma models can use an app-side helper that calculates the same kind of statistics from prompt parsing.

What it can do:

- Read a sheet from an Excel file in `workspace`
- Limit analysis to selected `target_columns`
- Filter rows with rules such as `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, and `contains`
- Group results by one or more columns with `group_by`
- Calculate `count`, `sum`, `mean`, `min`, `max`, `median`, `std`, and `nunique`

Example requests:

```text
workspace 의 sales.xlsx 에서 Sheet1 데이터를 읽고 amount 컬럼의 평균과 합계를 계산해줘
report.xlsx 의 Orders 시트에서 region 이 APAC 인 행만 필터링해서 revenue 통계를 보여줘
orders.xlsx 의 Data 시트에서 category 별로 sales 와 profit 평균을 계산해줘
```

Gemma behavior:

- When a Gemma model is selected, the app detects Excel file names such as `sales.xlsx`
- It tries to infer the target sheet, columns, group-by columns, filters, and requested statistics from the prompt
- The app calculates the statistics first and injects the result into the Gemma prompt
- The UI shows `Excel 통계 계산 중...` while this helper path runs

## Verify Shared RAG Wiring

Use the unit test:

```bash
python3 -m unittest /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/test_rag_pipeline.py
```

Use the model verification helper against cached markdown files:

```bash
python3 /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/verify_model_rag_pipeline.py --cache-dir /Users/tinyos/devel_opment/BerePi/apps/nextcloud --question "How does clipboard markdown upload to Nextcloud work?"
```

## Readme

이 앱은 `RTX 5090` 환경에서 `Streamlit` 과 `Ollama` 를 이용해 `gemma` 와 `qwen` 계열 모델을 함께 사용할 수 있도록 만든 인터페이스입니다. 기본 모델은 `gemma3:4b` 이며, 필요하면 사이드바에서 다른 모델을 선택하거나 직접 다운로드할 수 있습니다.

### 주요 기능

- 텍스트 질의응답
- Excel 업로드 및 시트 미리보기
- 이미지 업로드 및 모델 입력
- `workspace` 내부 파일 다운로드 및 삭제
- Nextcloud WebDAV 경로를 통한 Markdown/PDF 문서 RAG
- `qwen3:32b` 선택 가능
- `qwen3.5:9b` 선택 가능
- `qwen2.5-coder:7b`, `qwen3-coder:30b`, `qwen3.5:9b` 선택 시 workspace tool calling 지원
- `qwen2.5-coder:7b`, `qwen3-coder:30b`, `qwen3.5:9b` 선택 시 Excel 데이터 추출 및 통계 계산 tool 지원
- `gemma` 선택 시에도 프롬프트 기반 Excel 통계 계산 보조 기능 지원

### 모델별 동작

- `gemma` 계열 모델은 일반 질의응답 모드로 동작합니다.
- `qwen coder` 계열 모델은 일반 질의응답에 더해 workspace 파일 도구를 사용할 수 있습니다.
- WebDAV 에서 읽어온 RAG 문맥은 `gemma`, `qwen` 선택 모델 모두 공통으로 사용합니다.
- 즉, 모델마다 답변 스타일이나 tool calling 가능 여부는 다를 수 있지만, 문서 검색 결과 자체는 같은 흐름으로 연결됩니다.

### 설치 방법

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Ollama 준비

먼저 `Ollama` 서버를 실행합니다.

```bash
ollama serve
```

기본 Gemma 모델을 다운로드합니다.

```bash
ollama pull gemma3:4b
```

코딩형 모델도 함께 쓰려면 아래 모델을 추가로 받을 수 있습니다.

```bash
ollama pull qwen3:32b
ollama pull qwen3.5:9b
ollama pull qwen2.5-coder:7b
ollama pull qwen3-coder:30b
```

### 실행 방법

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
chmod +x run.sh
./run.sh
```

또는 직접 실행할 수 있습니다.

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 2280
```

### WebDAV / RAG 사용 방법

- 오른쪽 `WebDAV / RAG` 패널에서 Nextcloud WebDAV 주소와 계정 정보를 설정합니다.
- `WebDAV Base URL` 에는 서버 주소만 넣습니다. 예: `https://keties.mooo.com:22443`
- `Read Path 1` 부터 `Read Path 4` 에는 WebDAV 읽기 루트 경로를 넣습니다. 예: `/remote.php/dav/files/tinyos/`
- `Subdir Path` 에는 그 아래 공통 하위 디렉터리를 넣습니다. 예: `메모`
- 위 예시 조합은 `/remote.php/dav/files/tinyos/메모` 를 읽어서 RAG 를 구성합니다.
- 앱은 각 경로 아래의 `.md`, `.markdown`, `.pdf` 파일을 읽어서 간단한 lexical RAG 인덱스를 구성합니다.
- 사용자가 질문하면 현재 질문과 관련성이 높은 문서 조각을 찾아 프롬프트에 함께 넣습니다.
- 이 검색 문맥은 선택된 `gemma` 와 `qwen` 모델 모두에 공통으로 전달됩니다.

### 저장 위치와 설정

- 업로드된 Excel 파일은 `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/workspace` 에 저장됩니다.
- 앱 설정은 `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/app_settings.json` 에 저장됩니다.
- 모델 저장 경로를 바꿔도 실제 다운로드 위치를 바꾸려면 `Ollama` 를 `OLLAMA_MODELS` 환경변수와 함께 다시 시작해야 합니다.

### Tool Calling

- `qwen3:32b` 는 일반 대화용 Qwen 모델로 선택할 수 있습니다.
- `qwen2.5-coder:7b`, `qwen3-coder:30b`, `qwen3.5:9b` 를 선택하면 Ollama tool calling 을 통해 `workspace` 와 Excel 관련 도구를 사용할 수 있습니다.
- 새 `excel_calculate_statistics` tool 은 시트를 DataFrame 으로 읽고, 필터링과 컬럼 선택 후 통계를 계산할 수 있습니다.
- `gemma` 계열은 현재 이 앱에서 Ollama tool calling 을 직접 사용하지 않습니다.
- 대신 `gemma` 는 앱이 프롬프트를 먼저 해석해서 `workspace` 파일 내용을 읽어 프롬프트에 함께 넣는 방식으로 동작합니다.
- 이때 화면에는 `workspace 스캔 중...` 메시지가 표시됩니다.
- `gemma` 에서 Excel 통계 요청이 들어오면 앱이 먼저 통계를 계산해서 프롬프트에 함께 넣습니다.
- 이 경우 화면에는 `Excel 통계 계산 중...` 메시지가 표시됩니다.

현재 반영된 프롬프트 규칙은 아래와 같습니다.

- `작업파일 <파일명>`
- `작업파일: <파일명>`
- `작업파일 "<파일명>"`
- 프롬프트 안에 `notes/todo.md`, `config.json`, `report.txt` 같은 파일명이 직접 들어간 경우
- `파일 내용 알려줘`, `파일 읽어`, `workspace 에서 파일 찾아`, `read file`, `find file`, `check file` 같은 파일 읽기 의도 문장

동작 방식은 아래와 같습니다.

- `작업파일` 뒤에 온 값이 있으면 그 파일을 `workspace` 에서 우선 검색합니다.
- 경로 전체 일치, 하위 경로 일치, 파일명 일치, 확장자 없는 stem 일치 순으로 확인합니다.
- 찾으면 Python `open(..., encoding="utf-8", errors="replace")` 로 읽어서 모델 프롬프트에 넣습니다.
- 못 찾으면 UI 경고와 함께 `workspace 에서 찾지 못했습니다` 문맥을 모델에도 전달합니다.
- 일반 파일명 입력이나 파일 읽기 의도 문장은 `workspace` 텍스트 파일 스캔으로 처리합니다.

Excel 통계용 tool 은 아래 기능을 지원합니다.

- `workspace` 안의 Excel 파일 시트를 DataFrame 으로 읽기
- `target_columns` 로 특정 컬럼만 선택
- `filters` 로 행 필터링
- `group_by` 로 그룹 통계 생성
- `count`, `sum`, `mean`, `min`, `max`, `median`, `std`, `nunique` 계산

`gemma` 에서는 위 통계 기능이 프롬프트 해석 기반으로 동작합니다.

- 프롬프트에 `sales.xlsx`, `report.xlsx` 같은 Excel 파일명이 들어가야 합니다.
- 시트명이 프롬프트에 있으면 해당 시트를 우선 사용하고, 없으면 첫 번째 시트를 사용합니다.
- 컬럼명, `별로`, `평균`, `합계`, `최대`, `최소`, `건수`, `표준편차` 같은 표현을 보고 통계 계산 조건을 추론합니다.
- 예: `region 이 APAC 인 행만`, `category 별로`, `amount 평균` 같은 문장을 해석합니다.

예시 프롬프트:

```text
작업파일 notes/todo.md 읽어서 알려줘
작업파일: README
작업파일 "report.txt" 요약해줘
config.json 파일 내용 설명해줘
workspace 에서 memo.md 찾아서 알려줘
```

Excel 통계 예시 프롬프트:

```text
sales.xlsx 의 Sheet1 에서 amount 컬럼 평균과 합계를 계산해줘
report.xlsx 의 Orders 시트에서 region 이 APAC 인 행만 필터링해서 revenue 통계를 보여줘
orders.xlsx 의 Data 시트에서 category 별로 sales 와 profit 평균을 계산해줘
```

사용 가능한 도구 목록을 보고 싶으면 아래처럼 질문할 수 있습니다.

```text
사용가능한 tool 알려줘
tool 목록 알려줘
available tools
```

이때 동작은 아래와 같습니다.

- `qwen2.5-coder:7b`, `qwen3-coder:30b`, `qwen3.5:9b` 선택 시 현재 등록된 Ollama tool 이름과 설명 목록을 바로 보여줍니다.
- `qwen3:32b` 선택 시에는 coder 계열이 아니므로 tool calling 비활성 상태로 안내합니다.
- `gemma` 선택 시 현재 앱에서 Gemma가 직접 쓰는 Ollama tool calling 은 비활성이라고 안내하고, 대신 사용할 수 있는 `작업파일 <file>` 과 `workspace` 스캔형 프롬프트 기능을 보여줍니다.

### 웹 접근 로그인 설정

- 웹페이지 최초 접근 시 `ID` 와 `Password` 를 입력해야 앱 본문에 들어갈 수 있습니다.
- 서버에서 환경변수 `ZERONATIVE_APP_LOGIN_ID`, `ZERONATIVE_APP_LOGIN_PASSWORD` 를 설정하면 해당 값을 우선 사용합니다.
- 환경변수를 쓰지 않을 경우 `app_settings.json` 에 아래와 같이 넣어서 접근 계정을 지정할 수 있습니다.

```json
{
  "access_control": {
    "login_id": "your_id",
    "login_password": "your_password"
  }
}
```

### 검증 방법

공통 RAG 연결이 정상인지 테스트하려면 아래 단위 테스트를 실행합니다.

```bash
python3 -m unittest /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/test_rag_pipeline.py
```

실제 Markdown 캐시를 기준으로 모델별 공통 RAG 연결 상태를 확인하려면 아래 스크립트를 실행합니다.

```bash
python3 /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/verify_model_rag_pipeline.py --cache-dir /Users/tinyos/devel_opment/BerePi/apps/nextcloud --question "How does clipboard markdown upload to Nextcloud work?"
```

# Project Agent

Project Agent is a small local project workspace for:

- access-password protected landing page
- project name and management notes
- schedule and todo summary
- current storage directory tree
- file upload
- searchable uploaded-file database
- extracted metadata/content records saved as Markdown

The app uses only Python standard-library server/storage pieces by default:

- `http.server` for the local web server
- `sqlite3` for uploaded-file search metadata
- `data/extracted_md/*.md` for extracted file records

Optional extractors:

- `openpyxl` for `.xlsx` and `.xlsm`
- `python-docx` for `.docx`
- `pypdf` or `PyPDF2` for `.pdf`

## Run

```powershell
cd E:\devel\BerePi\apps\agentai\project_agent
.\run.ps1
```

Open:

```text
http://127.0.0.1:18765
```

On first launch, the page shows only the project title and access-password setup.
After login, the dashboard shows upload, schedule, todo summary, search, and
the storage directory tree.

## Gemma4 Integration

The dashboard can optionally connect to the local Gemma4 Ollama service from:

```text
E:\devel\BerePi\apps\deeplearning\LLM\5090\run_gemma4_ollama\server
```

Default connection:

```text
http://127.0.0.1:8082/api/generate
model: gemma4:31b
```

After login, open `Gemma4 Settings` and save the Gemma4 server URL, model, user
ID, and password. The `Gemma4 Assistant` panel can then answer project questions
using:

- project info
- schedule
- todos
- storage tree
- uploaded-file search matches
- extracted Markdown record paths

If Gemma4 or Ollama is not running, the dashboard remains usable. The assistant
panel shows the connection error, while upload/search/schedule/password features
continue normally.

Environment overrides:

```powershell
$env:PROJECT_AGENT_LLM_BASE_URL = "http://127.0.0.1:8082"
$env:PROJECT_AGENT_LLM_GENERATE_PATH = "/api/generate"
$env:PROJECT_AGENT_LLM_MODEL = "gemma4:31b"
$env:PROJECT_AGENT_LLM_TIMEOUT_SECONDS = "30"
```

## Storage

```text
data/
  config.json              # password hash and session secret
  project.md               # project name / management info
  schedule.md              # schedule notes
  todos.md                 # todo checklist
  project_agent.sqlite3    # uploaded-file index and search table
  uploads/                 # uploaded files
  extracted_md/            # extracted metadata/content Markdown records
```

## Search

Uploaded files are indexed by:

- file name
- author
- extracted file content

The extraction engine lives in:

```text
extract/engine.py
```

## Kanban Cards

The dashboard includes a lightweight Planka-inspired card board:

- Todo / Doing / Done columns
- card title and Markdown-style description
- assignee
- comma-separated labels
- due date
- uploaded-file attachment link
- recent comments
- quick move buttons
- per-worker completion confirmations
- manager completion confirmations for each worker

This is intentionally smaller than Planka. It does not implement realtime
multi-user sync, drag-and-drop ordering, project-level permissions, OpenID
Connect, or notification providers.

Worker names are entered in the assignee field as a comma-separated list. A
worker can mark their part as done, or a manager can confirm completion for that
worker. When all listed workers are confirmed, the card moves to `Done`.

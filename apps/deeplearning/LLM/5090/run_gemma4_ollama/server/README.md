# Gemma4 Ollama Server

This directory runs a local Gemma4 service page and JSON API backed by Ollama.
The default service port is `8082`, and the default Ollama model is
`gemma4:31b`.

The service can:

- start, stop, and check a local Ollama server
- pull the configured Ollama model when it is missing
- proxy text and image prompts to Ollama through `/api/generate`
- manage prompt authentication with `api_key.conf`
- save prompt history, user prompt history, and access logs
- select model and GPU from the web UI
- upload workspace files for prompt context
- run in foreground with `run_service.sh` or detached with `start.sh`

## Run

Foreground:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server
chmod +x run_service.sh start.sh stop.sh
./run_service.sh
```

Foreground with a custom service port:

```bash
./run_service.sh 8083
```

Detached:

```bash
./start.sh
```

Open:

```text
http://SERVER_IP:8082
```

If you started the service with a custom port, use that port in the URL.

The page checks:

- web server status
- Ollama reachability
- available Ollama models
- whether the selected Ollama model is available
- quick prompt tests through `/api/generate`
- prompt queue/result state
- recent prompts saved in `prompt_history.txt`
- user prompt history and access logs
- selected GPU and selected model
- workspace files
- Ollama server start through `/api/start-ollama`
- model unload through `/api/unload-model`
- Ollama server stop through `/api/stop-ollama`

## Startup Behavior

`run_service.sh` and `start.sh` both set defaults for the service and Ollama.

- `run_service.sh` runs the Python service in the foreground.
- `start.sh` starts the service detached and writes PID/log files.
- Both scripts discover or install `ollama` when needed.
- Both scripts start Ollama if `OLLAMA_BASE_URL` is not reachable.
- Both scripts pull `OLLAMA_MODEL` when it is missing and `AUTO_PULL=1`.
- Both scripts read `gpu-selection` and `model-selection` before starting Ollama.
- Both scripts refuse to start when the target service port is already occupied.

`run_service.sh` accepts one optional positional argument:

```bash
./run_service.sh 8083
```

This overrides `GEMMA4_SERVER_PORT` for that run. These forms are equivalent:

```bash
./run_service.sh 8083
GEMMA4_SERVER_PORT=8083 ./run_service.sh
```

`start.sh` does not currently accept a positional port argument. Use the
environment variable form:

```bash
GEMMA4_SERVER_PORT=8083 ./start.sh
```

## Prompt Authentication

Prompt calls through the web page and `POST /api/generate` require a user ID and
password from `api_key.conf`.

```json
{
  "enabled": true,
  "allow_only_user": "",
  "users": [
    {"id": "admin", "password": "change-me-now", "enabled": true},
    {"id": "operator", "password": "change-me-too", "enabled": true}
  ]
}
```

Set `allow_only_user` to one user ID, such as `admin`, to invalidate every other
account while leaving that one account active. Set it back to an empty string to
allow every enabled account again.

If `api_key.conf` does not exist, the service creates it from default values and
sets file permissions to `0600` when possible.

API clients can pass credentials with HTTP Basic Auth, with an authenticated web
session cookie, or with JSON fields:

```json
{"user_id": "admin", "password": "change-me-now", "prompt": "hello"}
```

The web UI can log in through `/api/session-login`, log out through
`/api/session-logout`, and save users through `/api/save-user`.

## Text and Image Prompts

Text clients can call:

```text
POST /api/generate
POST /api/enqueue-generate
GET  /api/prompt-result?id=JOB_ID
POST /api/cancel-pending-prompts
```

Vision/OCR clients can pass Ollama-compatible base64 images. The server forwards
`images` to Ollama's `/api/generate` payload.

```json
{
  "user_id": "admin",
  "password": "change-me-now",
  "prompt": "Extract all visible text from this image.",
  "images": ["base64-image-data"],
  "model": "vision-capable-model"
}
```

Use a model that supports image input. If the selected model is text-only, it may
ignore the image and hallucinate a plausible answer.

To verify image delivery without running model inference, call:

```text
POST /api/test-image-transfer
```

with the same authentication fields and an `images` array. The response includes
`image_count`.

## API

Health and status:

```text
GET /health
GET /api/status
```

Ollama controls:

```text
POST /api/start-ollama
POST /api/unload-model
POST /api/stop-ollama
```

Selection and session APIs:

```text
POST /api/select-gpu
POST /api/select-model
GET  /api/session-status
POST /api/session-login
POST /api/session-logout
POST /api/save-user
```

Logs, history, and workspace:

```text
GET  /api/prompt-history
GET  /api/user-prompt-history
GET  /api/access-log
GET  /api/workspace/files
POST /api/workspace/upload
```

`POST /api/workspace/upload` accepts authenticated JSON like:

```json
{
  "user_id": "admin",
  "password": "change-me-now",
  "files": [
    {
      "name": "notes.txt",
      "content": "prompt context"
    }
  ]
}
```

Uploaded files are stored under `workspace/`. Duplicate names receive a numeric
suffix.

## Stop

```bash
./stop.sh
```

`stop.sh` stops the detached Python service PID from `server.pid` and the Ollama
PID from `ollama.pid` when those files exist.

## Foreground

```bash
./run_service.sh
./run_service.sh 8083
GEMMA4_SERVER_PORT=8084 ./run_service.sh
./run_service.sh --help
```

By default `run_service.sh` starts Ollama locally on `127.0.0.1:11434`, uses an
already installed `gemma4:31b` model when present, pulls it only when missing,
and exposes the service page on `0.0.0.0:8082`.

## GPU and Model Selection

The service uses two small text files to persist UI selections:

- `gpu-selection`: selected GPU value, such as `auto`, `all`, `cpu`, `none`, or a GPU index
- `model-selection`: selected Ollama model name

When `gpu-selection` contains a GPU index and `nvidia-smi` is available, startup
maps that index to a GPU UUID before setting `CUDA_VISIBLE_DEVICES`. Set
`GEMMA4_CUDA_VISIBLE_USE_UUID=1` for API-side UUID mapping behavior where
supported.

When `model-selection` exists, startup uses it to override `OLLAMA_MODEL`.

Examples:

```bash
echo 0 > gpu-selection
echo gemma4:31b > model-selection
./run_service.sh
```

Use `cpu` or `none` in `gpu-selection` to force `CUDA_VISIBLE_DEVICES=-1`.

## systemd user service

```bash
mkdir -p ~/.config/systemd/user
cp gemma4-ollama-8082.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gemma4-ollama-8082.service
systemctl --user status gemma4-ollama-8082.service
```

## macOS LaunchAgent

```bash
mkdir -p ~/Library/LaunchAgents
cp com.berepi.gemma4-ollama-8082.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.berepi.gemma4-ollama-8082.plist
launchctl enable "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
launchctl kickstart -k "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
```

Stop it with:

```bash
launchctl bootout "gui/$(id -u)/com.berepi.gemma4-ollama-8082"
```

## Environment

- `OLLAMA_MODEL`: default `gemma4:31b`
- `OLLAMA_CONTEXT_LENGTH`: default `8192` so `gemma4:31b` fits on a 24 GB RTX 4090
- `OLLAMA_KEEP_ALIVE`: default `60m` to keep the loaded model warm between prompts
- `OLLAMA_BIN`: default discovered `ollama`, or `/usr/local/bin/ollama`
- `OLLAMA_PID_FILE`: default `ollama.pid` in this directory
- `API_KEY_CONF_FILE`: default `api_key.conf` in this directory
- `OLLAMA_BASE_URL`: default `http://127.0.0.1:11434`
- `OLLAMA_HOST`: default `127.0.0.1:11434`
- `GEMMA4_SERVER_HOST`: default `0.0.0.0`
- `GEMMA4_SERVER_PORT`: default `8082`
- `AUTO_PULL`: default `1`; set `0` to skip `ollama pull`
- `PROMPT_HISTORY_FILE`: default `prompt_history.txt` in this directory
- `GEMMA4_ACCESS_LOG_FILE`: default `logs/access.jsonl`
- `GEMMA4_SAMPLE_DIR`: default `sample` in this directory
- `GEMMA4_SERVER_WORKSPACE_DIR`: default `workspace` in this directory
- `GEMMA4_MACH_STATS_DIR`: default `mach_stats` in this directory
- `GEMMA4_REQUEST_TIMEOUT`: default `120`
- `GEMMA4_SESSION_TTL_SECONDS`: default `28800`
- `GEMMA4_SELECTED_MODEL`: runtime override for selected model
- `GEMMA4_SELECTED_GPU`: runtime override for selected GPU
- `GEMMA4_CUDA_VISIBLE_USE_UUID`: map selected GPU indexes to UUIDs when true

## Generated Files

The service may create or update these local files/directories:

```text
api_key.conf
gpu-selection
model-selection
ollama.pid
server.pid
prompt_history.txt
logs/
workspace/
mach_stats/
```

These files are runtime state and should generally not be committed.

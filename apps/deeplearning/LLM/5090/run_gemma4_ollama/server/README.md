# Gemma4 Ollama Server

This directory runs a small service page on port `8082` and uses local
Ollama as the backend for `gemma4`.

## Run

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server
chmod +x run_service.sh start.sh stop.sh
./start.sh
```

Open:

```text
http://SERVER_IP:8082
```

The page checks:

- web server status
- Ollama reachability
- available Ollama models
- whether `gemma4` is available
- a quick prompt test through `/api/generate`
- two prompt input boxes and recent prompts saved in `prompt_history.txt`
- Ollama server start through `/api/start-ollama`
- model unload through `/api/unload-model`
- Ollama server stop through `/api/stop-ollama`

## Stop

```bash
./stop.sh
```

## Foreground

```bash
./run_service.sh
```

By default `run_service.sh` starts Ollama locally on `127.0.0.1:11434`,
uses an already installed `gemma4` model when present, pulls it only when
missing, and exposes the service page on `0.0.0.0:8082`.

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

- `OLLAMA_MODEL`: default `gemma4`
- `OLLAMA_BIN`: default discovered `ollama`, or `/usr/local/bin/ollama`
- `OLLAMA_PID_FILE`: default `ollama.pid` in this directory
- `OLLAMA_BASE_URL`: default `http://127.0.0.1:11434`
- `OLLAMA_HOST`: default `127.0.0.1:11434`
- `GEMMA4_SERVER_HOST`: default `0.0.0.0`
- `GEMMA4_SERVER_PORT`: default `8082`
- `AUTO_PULL`: default `1`; set `0` to skip `ollama pull`
- `PROMPT_HISTORY_FILE`: default `prompt_history.txt` in this directory

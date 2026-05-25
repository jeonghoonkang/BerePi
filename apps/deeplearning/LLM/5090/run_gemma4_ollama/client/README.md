# ZeroNative Prompt Client

This directory contains a cross-platform desktop client shell for the
`run_gemma4_ollama/server` service.

The client uses:

- a local Python service for config storage, prompt history storage, and remote API proxying
- a small `zero-native` desktop shell that embeds the local client page

## Features

- direct server connection settings input
- JSON config import and export
- six prompt editors with per-prompt enable toggle
- per-prompt group assignment to `1`, `2`, or `3`
- grouped sequential execution
- prompt history list with delete and reload into any prompt slot
- works with the server auth and `/api/generate` flow used by:
  `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/server.py`

## Prompt Flow

- Group `1` prompts are combined and sent first.
- When Group `1` returns a response, Group `2` prompts are appended after that response and sent again.
- Group `3` repeats the same pattern using the Group `2` response.

Each selected group uses the previous model response as the base context for the
next group.

## Runtime Files

- config sample:
  [config/client_config.sample.json](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client/config/client_config.sample.json)
- saved config:
  `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client/data/client_config.json`
- prompt history:
  `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client/data/prompt_history.json`

## Start Local Client Service

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client
python3 client_service.py
```

Open:

```text
http://127.0.0.1:8765
```

## Start ZeroNative Shell

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client
chmod +x run_zero_native.sh
./run_zero_native.sh
```

The script starts the local client service if needed, then launches the
`zero-native` shell that embeds the local page.

## Requirements

- `python3`
- `zig` `0.16.0+`
- `node` and `npm`
- `zero-native` CLI

Install the CLI:

```bash
npm install -g zero-native
```

Clone the framework:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/client
git clone https://github.com/vercel-labs/zero-native.git third_party/zero-native
```

# ZeroNative RTX 5090

This directory now contains two things:

1. A real `zero-native` project scaffold based on the official `zero-native` app structure.
2. The earlier Python `Streamlit + Ollama` prototype files that were already in this folder.

The native shell files added for `zero-native` are:

- [app.zon](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/app.zon)
- [build.zig](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/build.zig)
- [build.zig.zon](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/build.zig.zon)
- [src/main.zig](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/src/main.zig)
- [src/runner.zig](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/src/runner.zig)
- [frontend/package.json](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/frontend/package.json)
- [frontend/index.html](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/frontend/index.html)
- [frontend/src/main.js](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/frontend/src/main.js)
- [frontend/src/styles.css](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/frontend/src/styles.css)
- [run_zero_native.sh](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/run_zero_native.sh)

## What Changed

This is no longer only a renamed Streamlit app directory. It now also includes an actual `zero-native` desktop shell layout using the same kind of files described in the official docs:

- `app.zon` for manifest, security, frontend, and window settings
- `build.zig` for native build, package, and dev commands
- `src/` for Zig application code
- `frontend/` for the web UI rendered inside the native WebView

Reference material used:

- [zero-native Quick Start](https://zero-native.dev/quick-start)
- [zero-native Frontend Projects](https://zero-native.dev/frontend)
- [zero-native app.zon Reference](https://zero-native.dev/app-zon)
- Official example structure from [vercel-labs/zero-native](https://github.com/vercel-labs/zero-native)

## Current Scope

The `zero-native` shell currently provides a real native project structure and a lightweight bundled frontend. It does **not** yet port every feature from the existing Streamlit/Ollama prototype into Zig or a native bridge.

The older prototype files are still present:

- [app.py](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/app.py)
- [run.sh](/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/run.sh)

Those Python files remain the feature-complete prototype for now.

## Prerequisites

You need the following tools on the host:

- `zig` `0.16.0+`
- `node` and `npm`
- `zero-native` CLI

Install the CLI:

```bash
npm install -g zero-native
```

## Framework Source Path

This scaffold expects the framework source at:

```bash
/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative/third_party/zero-native
```

Set it up like this:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
git clone https://github.com/vercel-labs/zero-native.git third_party/zero-native
```

Or override the path at build time:

```bash
zig build run -Dzero-native-path=/absolute/path/to/zero-native
```

## Run The Native Shell

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
chmod +x run_zero_native.sh
./run_zero_native.sh
```

Equivalent direct command:

```bash
zig build run -Dzero-native-path=/absolute/path/to/zero-native
```

`run_zero_native.sh` now checks these prerequisites before running:

- `zig` must be installed and available in `PATH`
- the `zero-native` framework must exist at `third_party/zero-native`
- or you can override the framework checkout path with `ZERO_NATIVE_PATH`

Example with an override:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
ZERO_NATIVE_PATH=/absolute/path/to/zero-native ./run_zero_native.sh
```

## Run In Dev Mode

This uses the managed frontend dev server flow from `zero-native`:

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
zig build dev
```

## Validate The Manifest

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
zero-native validate app.zon
```

## Package

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/zeronative
zig build package
```

## Notes

- The `zero-native` shell uses the `system` WebView by default.
- `build.zig` is adapted from the official `zero-native` example layout so it can run `zig build run`, `zig build dev`, and `zig build package`.
- The bundled frontend is intentionally small and acts as the native-shell starting point.
- Porting the full Streamlit UX into the `zero-native` frontend and Zig bridge would be the next implementation step.
- This environment did not have `zig` or `zero-native` installed at edit time, so the native build itself could not be executed here.

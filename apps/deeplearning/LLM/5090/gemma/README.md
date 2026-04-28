# Gemma 3 4B Streamlit App for RTX 5090

This app runs a Streamlit UI on port `2280` and sends prompts to a local
Ollama server using the `gemma3:4b` model by default. It can also use
`qwen2.5-coder:7b` for coding-oriented prompts and tool calling.

## Features

- Text chat with `gemma3:4b`
- Optional coding model support with `qwen2.5-coder:7b`
- Excel upload support for `.xlsx` and `.xls`
- Image upload support for `.png`, `.jpg`, `.jpeg`, `.webp`, and `.bmp`
- External access with Streamlit bound to `0.0.0.0:2280`
- Sidebar model selection, installed model refresh, and model download
- Auto-select the downloaded model as the active default
- GPU memory-based recommended Gemma model guidance when `nvidia-smi` is available
- Response elapsed time display after each prompt
- Current model information, local storage path, and model size display in the sidebar
- Uploaded Excel files are saved into the app-local `workspace` directory
- Gemma can use validated workspace tools to list, read, write, copy, and delete files
- User-selectable Ollama model storage path with model file migration support
- Qwen can use Excel tools for workbook info, sheet preview, cell read/write, range aggregation, workbook merge, and vertical stacking into one sheet

## Assumption

`gemma model 4` is implemented as the Ollama model `gemma3:4b`, which is the
current practical Gemma 4B-style multimodal target for text and image inputs.

## Install

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma
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

You can also download a larger Gemma model directly from the Streamlit sidebar.

For coding and file-tool prompts, you can also download:

```bash
ollama pull qwen2.5-coder:7b
```

## Run

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma
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
- Excel files are summarized into prompt context rather than being passed as raw binary.
- Uploaded Excel files are also saved into `/Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/gemma/workspace`.
- Excel tool calls support workbook inspection, sheet preview, cell reads/writes, numeric range operations such as `sum`, `average`, `min`, `max`, and `count`, plus multi-file merge in `append_rows` or `separate_sheets` mode, and single-sheet vertical stacking with configurable blank row gaps.
- The sidebar can refresh installed models via `GET /api/tags` and download models via `POST /api/pull`.
- The app tries to detect GPU memory using `nvidia-smi` and recommends a model size accordingly.
- The inferred storage path follows the local `OLLAMA_MODELS` setting or the default `~/.ollama/models` path.
- Workspace file tools are limited to the app-local `workspace` directory for safety.
- Changing the model storage path in the app updates the desired location and can move existing files, but Ollama must be restarted with `OLLAMA_MODELS` set to the same path for future downloads to use it.

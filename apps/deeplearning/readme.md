
# Deep Learning 

## PyTorch

## Dark-net (YOLO)

### Object detection based on deep learning

#### Run on RPI3 B+


#### Run on Jetson Nano


## TensorFlow

- Under testing
  - [install TensorFlow on raspberry pi](https://www.tensorflow.org/install/install_raspbian)


## other similar, reference
- https://github.com/Guanghan/ROLO
- https://github.com/felixchenfy , https://github.com/felixchenfy/Realtime-Action-Recognition
- https://github.com/eldar/pose-tensorflow

## LLM model download

Use `download_model.py` to fetch and cache open-source models such as Gemma, Llama, Qwen, or OpenAI's GPT-OSS variants. Models are stored under `apps/deeplearning/models` and the function returns the path for reuse:

```
python download_model.py --model gemma
```

Run `--list-models` or check `--help` to see all supported shorthands:

```
python download_model.py --list-models
```

Supported shorthand names include `gemma-3-270m`, `gemma-3-4b-it`, `llama`, `llama-7b`, `qwen`, `gpt-oss-120b`, and `gpt-oss-20b`.
You may also reference models by their full repo IDs, such as `openai/gpt-oss-120b`
or `openai/gpt-oss-20b`.

Other applications can import `download_model` from `download_model` to obtain the local path.

If a model requires authentication, place your Hugging Face access token in a
file named `hf_token.txt` (in this directory or the repository root) or set the
`HF_TOKEN` environment variable. The downloader will read the token
automatically when fetching models.

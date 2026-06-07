# Spark Docker Compose Runtime

This directory runs `../server.py` with Docker Compose and NVIDIA GPU access.
The container starts Ollama and then starts the Gemma4 Python service.

## Host Prerequisites

Install the NVIDIA GPU driver, Docker, and NVIDIA Container Toolkit on the host.
NVIDIA's current Docker configuration flow is:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

On Ubuntu/Debian, NVIDIA documents installing toolkit packages from the
`libnvidia-container` repository before running the Docker runtime configure
command.

## Run

```bash
cd /Users/tinyos/devel_opment/BerePi/apps/deeplearning/LLM/5090/run_gemma4_ollama/server/spark
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8082
```

Use another host port:

```bash
GEMMA4_SERVER_PORT=8083 docker compose up -d --build
```

Use another model:

```bash
OLLAMA_MODEL=gemma3:27b docker compose up -d --build
```

Limit visible GPUs:

```bash
NVIDIA_VISIBLE_DEVICES=0 docker compose up -d
```

## Logs and Stop

```bash
docker compose logs -f gemma4-server
docker compose down
```

Remove model/state volumes:

```bash
docker compose down -v
```

## Volumes

- `ollama-models`: Ollama model cache at `/root/.ollama`
- `gemma4-state`: `api_key.conf`, prompt history, and user prompt history
- `gemma4-logs`: service and Ollama logs
- `gemma4-workspace`: uploaded workspace files
- `gemma4-mach-stats`: runtime statistics

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      procps \
      python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY server.py /app/server.py
COPY api_key.conf.sample /app/api_key.conf.sample
COPY sample /app/sample
COPY spark/entrypoint.sh /usr/local/bin/gemma4-entrypoint

RUN chmod +x /usr/local/bin/gemma4-entrypoint \
    && mkdir -p /app/state /app/logs /app/workspace /app/mach_stats

EXPOSE 8082

ENTRYPOINT ["/usr/local/bin/gemma4-entrypoint"]

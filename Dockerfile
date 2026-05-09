FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client ca-certificates docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY sophie.py tela.py ./

RUN uv sync --frozen --no-dev

COPY docker/backend-entrypoint.sh /usr/local/bin/nexus-backend-entrypoint
RUN chmod +x /usr/local/bin/nexus-backend-entrypoint

ENTRYPOINT ["nexus-backend-entrypoint"]
CMD ["uv", "run", "uvicorn", "src.server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

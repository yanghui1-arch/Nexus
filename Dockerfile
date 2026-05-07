# ─── Stage 1: Build ───
FROM python:3.12-slim AS builder

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies in a cached layer
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ─── Stage 2: Runtime ───
FROM python:3.12-slim AS runtime

# Only runtime system deps: git for code agents, libpq for asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends git libpq5 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY src/ /app/src/

# Copy the entrypoint
COPY docker/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]

#!/bin/sh
set -e

# ── Nexus Docker Entrypoint ──
# Usage:
#   docker run ... nexus:latest api          → start FastAPI (uvicorn)
#   docker run ... nexus:latest worker       → start Celery worker
#
# Environment variables (see .env.example):
#   NEXUS_API_KEY, NEXUS_BASE_URL, NEXUS_MODEL, etc.

CMD="${1:-api}"

case "$CMD" in
    api)
        echo "Starting Nexus API server..."
        exec uvicorn src.server.api.main:app --host 0.0.0.0 --port "${NEXUS_API_PORT:-8000}"
        ;;
    worker)
        echo "Starting Nexus Celery worker..."
        exec celery -A src.server.celery.app worker \
            --loglevel="${CELERY_LOGLEVEL:-info}" \
            --concurrency="${CELERY_CONCURRENCY:-4}" \
            --queues="${NEXUS_CELERY_QUEUE:-nexus_agent_tasks}"
        ;;
    *)
        echo "Unknown command: $CMD"
        echo "Usage: docker-entrypoint.sh [api|worker]"
        exit 1
        ;;
esac

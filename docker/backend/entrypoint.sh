#!/usr/bin/env sh
set -eu

role="${1:-api}"
shift || true

case "$role" in
  api)
    exec uvicorn src.server.api.main:app --host 0.0.0.0 --port "${NEXUS_API_PORT:-6515}" "$@"
    ;;
  worker)
    exec celery -A src.server.celery.app:celery_app worker \
      --loglevel "${NEXUS_CELERY_LOG_LEVEL:-INFO}" \
      --queues "${NEXUS_CELERY_QUEUE:-nexus_agent_tasks}" "$@"
    ;;
  poller)
    exec python -m src.server.pollers "$@"
    ;;
  *)
    exec "$role" "$@"
    ;;
esac

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_compose_wires_core_services() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text()

    for service in ["postgres:", "redis:", "api:", "worker:", "web:"]:
        assert service in compose

    assert "postgres-data:/var/lib/postgresql/data" in compose
    assert "redis-data:/data" in compose
    assert "agent-workspaces:/workspace" in compose
    assert "condition: service_healthy" in compose


def test_production_env_uses_compose_service_hosts() -> None:
    env = (ROOT / ".env.production.example").read_text()

    assert "@postgres:5432/nexus" in env
    assert "redis://redis:6379/0" in env
    assert "POSTGRES_PASSWORD=change_me_strong_password" in env
    assert "your_" not in env


def test_container_entrypoints_expose_expected_roles() -> None:
    entrypoint = (ROOT / "docker/backend/entrypoint.sh").read_text()
    nginx = (ROOT / "docker/frontend/nginx.conf").read_text()

    assert "uvicorn src.server.api.main:app" in entrypoint
    assert "celery -A src.server.celery.app:celery_app worker" in entrypoint
    assert "proxy_pass http://api:8000/v1/" in nginx
    assert "try_files $uri $uri/ /index.html" in nginx

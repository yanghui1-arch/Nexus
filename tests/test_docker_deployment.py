from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compose_declares_required_services_versions_and_ports() -> None:
    compose = read("docker-compose.yml")

    for service in ("nginx", "web", "backend", "worker", "postgres", "redis"):
        assert re.search(rf"^  {service}:$", compose, re.MULTILINE)

    assert "image: postgres:18" in compose
    assert "image: redis:7.4" in compose
    assert '"16315:80"' in compose
    assert '"16319:8080"' in compose


def test_compose_wires_runtime_dependencies() -> None:
    compose = read("docker-compose.yml")

    assert "@postgres:5432/" in compose
    assert "redis://redis:6379/0" in compose
    assert "condition: service_healthy" in compose
    assert "/var/run/docker.sock:/var/run/docker.sock" in compose
    assert "nexus-workspaces:/workspace" in compose


def test_nginx_routes_frontend_backend_and_healthcheck() -> None:
    nginx_conf = read("docker/nginx.conf")

    assert "server web:80;" in nginx_conf
    assert "server backend:8000;" in nginx_conf
    assert "listen 80;" in nginx_conf
    assert "listen 8080;" in nginx_conf
    assert "location /v1/" in nginx_conf
    assert "location /health" in nginx_conf


def test_application_images_have_expected_entrypoints() -> None:
    backend_dockerfile = read("Dockerfile")
    web_dockerfile = read("web/Dockerfile")
    web_nginx = read("web/docker/nginx-web.conf")

    assert "FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim" in backend_dockerfile
    assert "ENTRYPOINT [\"nexus-backend-entrypoint\"]" in backend_dockerfile
    assert "src.server.api.main:app" in backend_dockerfile
    assert "FROM node:24-bookworm-slim AS build" in web_dockerfile
    assert "FROM nginx:1.29-bookworm" in web_dockerfile
    assert "try_files $uri $uri/ /index.html;" in web_nginx

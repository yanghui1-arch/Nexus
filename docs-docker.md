# Docker deployment

This repository includes a Docker Compose stack for a one-command Ubuntu 22.04 deployment.
Compose is the right fit here because Nexus is split into multiple cooperating services:

- web frontend, served by Nginx
- Nexus FastAPI backend
- Celery worker
- Nginx reverse proxy/load balancer
- PostgreSQL 18
- Redis 7.4

## Ports

- Frontend: `http://SERVER_IP:16315`
- Backend: `http://SERVER_IP:16319`

The frontend port also proxies `/v1/*` and `/health` to the backend, so browser requests can stay same-origin.

## Ubuntu 22.04 setup

Install Docker Engine and the Compose plugin, then deploy:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## One-command deployment

From the repository root:

```bash
cp .env.docker.example .env.docker
# Edit .env.docker and set API keys, GitHub tokens, repo, and a strong POSTGRES_PASSWORD.
docker compose --env-file .env.docker up -d --build
```

Check status:

```bash
docker compose ps
docker compose logs -f backend worker nginx
curl http://localhost:16319/health
```

Stop the stack:

```bash
docker compose down
```

To remove database/Redis/workspace volumes as well:

```bash
docker compose down -v
```

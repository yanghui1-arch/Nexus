# Docker deployment on Ubuntu 22.04

This stack runs Nexus on one Ubuntu 22.04 server with Docker Compose:

- `web`: nginx serving the React/Vite dashboard and proxying API calls.
- `api`: FastAPI service.
- `worker`: Celery worker for agent execution.
- `postgres`: PostgreSQL 18 with a named data volume.
- `redis`: Redis broker/cache with append-only persistence.

## 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in so the Docker group is active.

## 2. Configure Docker registry mirror

On Ubuntu servers in China, configure the 1ms Docker registry mirror before building images:

```bash
bash <(curl -sSL https://n3.ink/helper)
```

Choose the Docker image acceleration option in the helper. If you prefer to manage Docker manually, write the mirror configuration and restart Docker:

```bash
echo '{"registry-mirrors":["https://docker.1ms.run"],"dns":["8.8.8.8","114.114.114.114"]}' \
  | sudo tee /etc/docker/daemon.json >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart docker
```

## 3. Configure Nexus

```bash
git clone https://github.com/yanghui1-arch/Nexus.git
cd Nexus
cp .env.production.example .env.production
chmod 600 .env.production
$EDITOR .env.production
```

Set real OpenAI-compatible API credentials, GitHub tokens, repository name, and a strong `POSTGRES_PASSWORD`. Keep `NEXUS_DATABASE_URL` in sync with the Postgres credentials.

## 4. Start or update production

```bash
./scripts/deploy-production.sh
```

Open `http://SERVER_IP:6515/` for the dashboard. The API health endpoint is `http://SERVER_IP:6515/health`.

## 5. Operations

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs -f api
docker compose --env-file .env.production -f docker-compose.production.yml logs -f worker
docker compose --env-file .env.production -f docker-compose.production.yml down
```

Back up the named volumes regularly, especially `postgres-data`. If this server is internet-facing, put TLS in front of port 80 with your preferred reverse proxy or cloud load balancer.

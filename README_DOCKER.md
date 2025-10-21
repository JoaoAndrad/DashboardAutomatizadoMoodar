Docker Hub distribution guide for Moodar App

## Overview

This repository includes Docker configuration to build the application image and a development compose file. We publish the production image to Docker Hub so other machines can pull it and run it with Docker.

## Publish target

We expect the Docker Hub repository name to be: <DOCKERHUB_USERNAME>/moodar-app
Replace <DOCKERHUB_USERNAME> with your Docker Hub username or organization.

## GitHub Actions

A workflow was added at `.github/workflows/publish-docker-hub.yml`. It will build and push the image to Docker Hub when commits are pushed to `main` or when tags matching `v*` are created.

Required repository secrets (GitHub):

- DOCKERHUB_USERNAME — your Docker Hub username
- DOCKERHUB_TOKEN — a Docker Hub access token (create at https://hub.docker.com/settings/security)

## Manual publish (local)

If you want to push an image manually from your machine:

```powershell
# build
docker build -f Dockerfile -t yourdockerhubuser/moodar-app:latest .
# login
docker login --username yourdockerhubuser
# push
docker push yourdockerhubuser/moodar-app:latest
```

## Client instructions (machines that will run the app)

1. Install Docker (Docker Desktop on Windows/macOS or Docker Engine on Linux).
2. Pull the image:

```powershell
docker pull yourdockerhubuser/moodar-app:latest
```

3. Run with Docker Compose (example):

```powershell
# create a minimal docker-compose.yml that references the published image
cat > docker-compose.yml <<EOF
version: '3.8'
services:
  app:
    image: yourdockerhubuser/moodar-app:latest
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
EOF

# then bring up
docker compose up -d
```

## Updating to new versions

When you publish a new image (via CI or manual push), other machines can update by running:

```powershell
docker pull yourdockerhubuser/moodar-app:latest
docker compose up -d
```

## Security notes

- Do not expose the Selenium service publicly without authentication; keep it in an internal network or run it only for local/dev use.
- For production, place a reverse proxy (nginx/Caddy) in front and enable TLS.

If you want, I can:

- create the docker hub repository and push an initial image (you must provide Docker Hub credentials or do the final `docker login`),
- or create the GitHub Actions secrets and finish a full CI setup (I will add step-by-step instructions for creating the secrets).

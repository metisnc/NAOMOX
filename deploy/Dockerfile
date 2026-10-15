# Image optionnelle (alternative au LXC + install.sh). Contexte de build : racine du dépôt.
#   docker compose -f deploy/docker-compose.yml up -d --build
FROM node:22-alpine AS front
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
RUN useradd --system --home-dir /srv/naomox --shell /usr/sbin/nologin naomox
WORKDIR /opt/naomox
COPY backend/pyproject.toml backend/README.md app/
COPY backend/src app/src
RUN pip install --no-cache-dir ./app
COPY --from=front /src/dist /opt/naomox/frontend
COPY deploy/config.example.yaml /etc/naomox/config.yaml
ENV NAOMOX_CONFIG=/etc/naomox/config.yaml PYTHONUNBUFFERED=1
RUN mkdir -p /srv/naomox && chown naomox:naomox /srv/naomox
USER naomox
EXPOSE 8080
CMD ["naomox", "serve", "--port", "8080"]

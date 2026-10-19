# ─────────────────────────────────────────────────────────
# Image gobgp-cli  –  sans accès internet (pas de apk add)
# ─────────────────────────────────────────────────────────
# FROM registry.example.com/dockerhub/library/alpine:3.20
FROM registry.example.com/dockerhub/library/ubuntu:22.04

ARG HTTP_PROXY
ARG HTTPS_PROXY

ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY
ENV TZ=Europe/Paris

RUN apt-get update && apt-get install -y \
    cron \
    bash \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY bin/gobgp /opt/gobgp/gobgp

# Le chargement vers ClickHouse (lorion03vel) tourne côté hôte
# (voir lorion01vel/gobgp/scripts/load_clickhouse.sh), pas dans ce conteneur.

RUN mkdir -p /data/gobgp
# # ── Crontab ─────────────────────────────────────────────
RUN mkdir -p /var/log/gobgp

COPY client/crontab /etc/crontab

RUN chmod +x /opt/gobgp/gobgp \
    && ln -s /opt/gobgp/gobgp /usr/local/bin/gobgp

COPY client/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
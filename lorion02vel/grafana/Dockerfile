# ============================================================
# Dockerfile — Grafana + plugin ClickHouse (lorion02vel)
#
# Les conteneurs du lab n'ont pas d'accès internet : le plugin est installé
# AU BUILD, via le proxy d'entreprise transmis en build-arg (même pattern que
# netbox-neo4j-sync). À l'exécution, aucun appel sortant.
# ============================================================
ARG REGISTRY=registry.example.com/dockerhub
ARG GRAFANA_VERSION=12.1.1
FROM ${REGISTRY}/grafana/grafana:${GRAFANA_VERSION}

# Proxy uniquement pour le téléchargement du plugin (portée : ce stage).
ARG http_proxy
ARG https_proxy
ARG CLICKHOUSE_PLUGIN_VERSION=""

# grafana-clickhouse-datasource : datasource officielle ClickHouse.
# Version épinglable via CLICKHOUSE_PLUGIN_VERSION (vide = dernière compatible).
RUN grafana cli ${CLICKHOUSE_PLUGIN_VERSION:+--pluginVersion ${CLICKHOUSE_PLUGIN_VERSION}} \
    plugins install grafana-clickhouse-datasource

# Entrypoint enveloppant : exporte les secrets *__FILE en variables d'env
# pour l'interpolation des fichiers de provisioning, puis rend la main au
# run.sh de l'image officielle.
COPY --chmod=755 entrypoint-secrets.sh /entrypoint-secrets.sh
ENTRYPOINT ["/entrypoint-secrets.sh"]

# ============================================================
# Documentation Orion — image conteneurisée
# Étape 1 : build statique du site avec MkDocs (Material)
# Étape 2 : service via nginx (léger, robuste pour du statique)
# ============================================================

# ---- Étape 1 : build ----
FROM registry.example.com/dockerhub/library/python:3.12-slim AS builder

# Proxy uniquement pour le build (pip/PyPI) — le conteneur n'a pas d'accès direct.
ARG http_proxy
ARG https_proxy

WORKDIR /docs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mkdocs.yml .
COPY docs/ ./docs/
# --strict échoue sur tout lien cassé / page hors nav.
RUN mkdocs build --strict

# ---- Étape 2 : service ----
FROM registry.example.com/dockerhub/library/nginx:1.27-alpine

# Serveur nginx personnalisé : gzip + en-têtes de cache (remplace le default.conf).
COPY nginx-default.conf /etc/nginx/conf.d/default.conf

# Site statique généré à l'étape précédente.
COPY --from=builder /docs/site /usr/share/nginx/html

EXPOSE 80

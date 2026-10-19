# NetBox — Configuration

!!! info "Configuration gérée par netbox-docker"
    La configuration complète de NetBox relève du projet **`/home/services/netbox-docker/`**.
    Cette page recense les éléments **utiles à l'intégration** et observés réellement.

## Fichiers d'environnement (`env/`)

| Fichier | Concerne |
|---------|----------|
| `env/netbox.env` | Application NetBox (DB, Redis, e-mail, superuser…) |
| `env/postgres.env` | PostgreSQL |
| `env/redis.env` | Redis (files RQ) |
| `env/redis-cache.env` | Redis-cache |

Chaque fichier possède un `.example` versionné.

## Variables NetBox notables (`env/netbox.env`)

| Groupe | Variables |
|--------|-----------|
| Base de données | `DB_HOST=postgres`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Redis (RQ) | `REDIS_HOST`, `REDIS_PASSWORD`, `REDIS_DATABASE` |
| Redis (cache) | `REDIS_CACHE_HOST`, `REDIS_CACHE_PASSWORD`, `REDIS_CACHE_DATABASE` |
| E-mail | `EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_USE_TLS`, … |

!!! warning "Cohérence inter-fichiers"
    `DB_*` (netbox) ↔ `POSTGRES_*` (postgres) et `REDIS_*` (netbox) ↔ `REDIS_PASSWORD` (redis)
    doivent être alignés, sinon NetBox ne démarre pas.

## Image `-plugins` (override)

`docker-compose.override.yml` construit une image locale enrichie de plugins :

```yaml
netbox:
  image: netbox:${VERSION-v4.5.4-4.0.1}-plugins
  pull_policy: never
  build:
    context: .
    dockerfile: Dockerfile-Plugins
    args:
      VERSION: ${VERSION:-v4.5.4-4.0.1}
      HTTP_PROXY: ${http_proxy}
      HTTPS_PROXY: ${https_proxy}
      NO_PROXY: ${no_proxy}
  ports:
    - 9999:8080
```

- Le **proxy** est nécessaire au build (installation des plugins).
- Publication **9999 → 8080**.

## Configuration côté intégration (posée par le sync)

Ces objets sont créés **dans NetBox** par le CLI d'administration du sync (pas dans les fichiers
netbox-docker) :

- un **API Token** (manuel : Admin → API Tokens) ;
- un **Webhook** + une **Event Rule** (`admin setup-webhooks`).

Voir [Intégration](integration.md) et
[netbox-neo4j-sync / CLI](../netbox-neo4j-sync/admin-cli.md).

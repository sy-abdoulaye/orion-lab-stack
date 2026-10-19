# ClickHouse — Déploiement

## État actuel : actif

Le service est **inclus** dans l'`include` du Compose parent
(`lorion03vel/docker-compose.yml`) et démarre avec la stack :

```yaml
include:
  - path: clickhouse/compose.yml
    env_file: clickhouse/.env
  - path: neo4j/compose.yml
    env_file: neo4j/.env
  - path: netbox-neo4j-sync/compose.yml
    env_file: netbox-neo4j-sync/.env
  - path: gobgp-neo4j-sync/compose.yml
    env_file: gobgp-neo4j-sync/.env
```

## Première installation (nouvelle VM)

1. **Créer les secrets** (hors git), alignés aux hashs des XML :
   ```bash
   cd orion-lab-stack/lorion03vel/clickhouse
   mkdir -p secrets
   printf 'lorion03vel' > secrets/clickhouse_password          # = SHA256 dans lorion03vel.xml
   printf 'pwd!'        > secrets/clickhouse_admin_password     # = SHA256 dans admin.xml
   chmod 600 secrets/*
   ```
2. **Démarrer la stack** :
   ```bash
   cd orion-lab-stack/lorion03vel
   make up        # crée le réseau lorion03vel-network si absent, puis compose up
   ```

!!! note "Réseau"
    Le réseau `lorion03vel-network` est `external: true` : son cycle de vie est géré par le
    **Makefile de la VM** (`make network` / `make purge`), jamais par `docker network create`
    à la main.

## Vérification du bon fonctionnement

=== "Healthcheck / ping"

    ```bash
    docker compose ps clickhouse
    docker exec lorion03vel-clickhouse \
      wget -qO- http://127.0.0.1:8123/ping   # -> Ok.
    ```

=== "Connexion applicative"

    ```bash
    docker exec -it lorion03vel-clickhouse \
      clickhouse-client -u lorion03vel --password 'lorion03vel' -q "SELECT version();"
    ```

=== "Vérifier l'init"

    ```bash
    docker exec lorion03vel-clickhouse clickhouse-client -u lorion03vel --password 'lorion03vel' \
      -q "SHOW DATABASES; SHOW TABLES FROM mydb;"
    # bases : lorion03vel (CLICKHOUSE_DB) + mydb (schema.sql)
    ```

!!! success "Résultat attendu"
    - `/ping` renvoie `Ok.`
    - Bases `lorion03vel` et `mydb` présentes ; tables `events`, `metrics`,
      `events_hourly_agg` dans `mydb`.
    - Utilisateurs `admin`, `lorion03vel` (XML) + `app_backend`, `bi_reader`, `db_migrator` (SQL).

## Première initialisation uniquement

!!! warning
    Les scripts `init/*.sql` ne s'exécutent qu'au **premier démarrage** (volume `clickhouse_data`
    vide). Pour rejouer l'init, il faut supprimer le volume (perte de données) — voir
    [Maintenance](maintenance.md).

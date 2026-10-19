# ClickHouse — Monitoring

## Healthcheck

Défini dans `clickhouse/compose.yml`, basé sur l'endpoint **`/ping`** (sans authentification —
ne dépend d'aucun mot de passe) :

```yaml
healthcheck:
  test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:8123/ping"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

!!! info "Pourquoi `/ping` plutôt que `SELECT 1`"
    `/ping` ne requiert pas d'authentification, contrairement à `clickhouse-client SELECT 1` qui
    hériterait de `CLICKHOUSE_USER`. Le healthcheck reste ainsi indépendant des mots de passe.

```bash
docker inspect --format '{{.State.Health.Status}}' lorion03vel-clickhouse
docker exec lorion03vel-clickhouse wget -qO- http://127.0.0.1:8123/ping   # -> Ok.
```

## Logs

- Niveau `information` (défini dans `override.xml`).
- `docker compose logs -f clickhouse`.
- Le volume de logs (`/var/log/clickhouse-server`) est **commenté** dans le compose ; les logs
  passent par la sortie standard du conteneur.

## Tables système utiles

```sql
-- Requêtes récentes
SELECT query, query_duration_ms, read_rows
FROM system.query_log
WHERE type = 'QueryFinish'
ORDER BY event_time DESC LIMIT 20;

-- Taille des tables
SELECT database, table, formatReadableSize(sum(bytes)) AS size
FROM system.parts WHERE active GROUP BY database, table ORDER BY sum(bytes) DESC;

-- Utilisateurs / rôles / quotas
SELECT name FROM system.users;
SELECT name FROM system.roles;
SELECT * FROM system.quotas;
```

## Performances

- Moteur `MergeTree` : le **partitionnement** (`PARTITION BY toYYYYMM(...)`) et l'`ORDER BY`
  conditionnent la performance des requêtes.
- La table `events` applique un **TTL de 12 mois** (`TTL created_at + INTERVAL 12 MONTH`) —
  purge automatique des vieilles données.
- La **vue matérialisée** `mv_events_hourly` pré-agrège les événements par heure vers
  `events_hourly_agg` (SummingMergeTree).

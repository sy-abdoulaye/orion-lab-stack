# Monitoring

La supervision repose sur les **healthchecks Docker**, les **logs** des conteneurs et des
**requêtes de contrôle** par service. Pour la visualisation des données,
[Grafana](../services/grafana/index.md) (lorion02vel) interroge ClickHouse en lecture
seule ; pas de métrologie centralisée (Prometheus) à ce jour —
cf. [Roadmap](../architecture/roadmap.md).

## Vue d'ensemble

```bash
docker compose ps         # état + santé de tous les services du projet
```

| Service | Healthcheck réel | Vérification manuelle |
|---------|------------------|-----------------------|
| Neo4j | `cypher-shell … 'RETURN 1'` | `RETURN apoc.version(), gds.version()` |
| ClickHouse | `wget /ping` | `SELECT version()` |
| receiver | `GET /healthz` (Neo4j joignable) | `admin stats` |
| reconciler | *(pas de healthcheck)* | logs « Cycle terminé » |
| reconciler gobgp | *(pas de healthcheck)* | logs « Cycle topologie/monitor terminé » |
| Documentation (nginx) | `wget http://localhost:80/` | `curl http://<hôte>:8090/` |
| gobgpd (lorion01vel) | `gobgp global` (gRPC local) | `sh gobgp.sh neighbors` (sessions `Establ`) |
| gobgp-cli (lorion01vel) | *(pas de healthcheck)* | CSV `data/` qui évoluent, `logs-cron` |
| vector (lorion01vel) | *(pas de healthcheck)* | logs + `max(Age)` des tables `monitor_bgp_*` |
| NetBox | `curl /login/` | `GET /api/status/` |
| PostgreSQL | `pg_isready` | `psql \dt` |
| Redis/Valkey | `valkey-cli ping = PONG` | — |

## Healthchecks

```bash
docker inspect --format '{{.Name}} -> {{.State.Health.Status}}' \
  lorion03vel-neo4j netbox-neo4j-sync-receiver 2>/dev/null
```

!!! info "Rappels"
    - Neo4j utilise `cypher-shell` (l'image n'a pas `curl`).
    - ClickHouse utilise `/ping` (indépendant de l'authentification).
    - Le **reconciler** n'a pas de healthcheck : on surveille ses **logs de cycle**.

## Logs

```bash
docker compose logs -f neo4j
docker compose logs -f receiver
docker compose logs --since 1h reconciler | grep -E "Cycle terminé|Échec|Traceback"
# NetBox worker (émission des webhooks)
docker logs -f netbox-docker-netbox-worker-1
```

## Indicateurs applicatifs

```bash
# Volumétrie du graphe
docker compose run --rm reconciler python -m admin stats

# Directement en Cypher
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (n) RETURN count(n); MATCH ()-[r:EST_CONNECTE_A]->() RETURN count(r);"
```

## Signaux à surveiller

| Signal | Interprétation |
|--------|----------------|
| reconciler « Échec du cycle » | NetBox injoignable / token invalide / Neo4j down |
| receiver 401 répétés | `WEBHOOK_SECRET` désaligné |
| receiver 400 répétés | format de payload inattendu |
| Neo4j `unhealthy` | mauvais secret / moteur KO (voir dépannage) |
| worker NetBox sans logs webhook | Event Rule absente ou worker arrêté |
| reconciler gobgp : ratio « rattachés » bas | Noms BGP-LS ≠ noms NetBox (données, pas bug) |
| `max(Age)` vieux dans `monitor_bgp_*` | Chaîne amont cassée (gobgp monitor ou vector) |
| `load_clickhouse.log` en `[FAIL]` | ClickHouse injoignable / secret writer invalide |
| Sessions BGP hors `Establ` | Réflecteurs injoignables / conf gobgpd (voir [gobgp](../services/gobgp/troubleshooting.md)) |

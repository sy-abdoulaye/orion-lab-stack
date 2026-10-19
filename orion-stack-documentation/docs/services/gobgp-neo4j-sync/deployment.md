# gobgp-neo4j-sync — Déploiement

Le service fait partie du projet Compose `lorion03vel` (via l'`include` du parent) :
il démarre avec `make up`.

## Première installation

### 1. Utilisateur ClickHouse en lecture seule

`gobgp_writer` (SELECT+INSERT) serait trop large pour ce service. Exécuter **une fois**
`lorion01vel/gobgp/schemas/01_reader_role.sql` (après avoir remplacé `<MOT_DE_PASSE>`)
avec un compte admin ClickHouse, puis reporter le mot de passe dans
`secrets/ch_gobgp_reader_password` (`chmod 600`, hors git).

### 2. Configuration

```bash
cd lorion03vel/gobgp-neo4j-sync
cp .env.example .env          # que du non-sensible (versionné)
mkdir -p secrets && chmod 700 secrets
printf '%s' '<mdp gobgp_reader>' > secrets/ch_gobgp_reader_password
printf '%s' '<mdp neo4j>'        > secrets/neo4j_password
chmod 600 secrets/*
# BUILD_*_PROXY dans .env si le build doit joindre PyPI via le proxy
```

### 3. Démarrage

```bash
cd lorion03vel
make up                                   # build + up de toute la stack
docker compose logs -f reconciler-gobgp-neo4j
```

## Bootstrap / administration (CLI)

```bash
docker compose run --rm reconciler-gobgp-neo4j python -m admin <commande>
```

| Commande | Rôle |
|----------|------|
| `stats` | Compteurs du graphe (nœuds par label, relations par type) |
| `init` | Full-sync immédiat (cycle topologie + cycle monitor) |
| `wipe [--yes]` | Purge les données de **cette** synchro : relations `ISIS`/`ANNOUNCES_*`, nœuds `:Prefix`, propriétés BGP des équipements — ne touche pas aux nœuds NetBox |

## Vérifications

```bash
docker compose logs reconciler-gobgp-neo4j | grep "Cycle topologie terminé"
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (a)-[l:ISIS]->(b) RETURN a.Nom, b.Nom, l.IgpMetric LIMIT 5"
```

!!! success "Service opérationnel"
    - Logs : `Cycle topologie terminé : N/M routeur(s) rattachés…` toutes les 5 min,
      `Cycle monitor terminé` toutes les 20 s.
    - Relations `ISIS` / `ANNOUNCES_PREFIX` / `ANNOUNCES_ROUTE` présentes dans Neo4j.

!!! note "Ordre de démarrage"
    Le service suppose que `netbox-neo4j-sync` a déjà créé les nœuds équipement : sans
    eux, les routeurs sont comptés « sans équipement correspondant » et rien n'est
    greffé (le compteur redescend dès que les équipements existent).

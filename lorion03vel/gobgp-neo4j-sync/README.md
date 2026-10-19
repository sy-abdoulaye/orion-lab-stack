# gobgp-neo4j-sync

Synchronise la topologie BGP-LS collectée par GoBGP (base ClickHouse `gobgp`,
conteneur `lorion03vel-clickhouse`) vers Neo4j, en la greffant sur les nœuds
équipement déjà créés par `netbox-neo4j-sync` (adjacences IGP, préfixes
annoncés).

- **Architecture** : un seul service `reconciler`, deux boucles internes —
  topologie (pull complet périodique) + monitor (flux d'événements
  incrémental, met à jour `Withdraw` sans recréer les relations). **Pas de
  receiver** : ClickHouse ne pousse rien.
- Ni ClickHouse ni Neo4j ne sont gérés ici : ils tournent déjà sur
  `lorion03vel-network` (`bolt://lorion03vel-neo4j:7687`,
  `lorion03vel-clickhouse:9000` en protocole natif — toujours passer par le
  réseau Docker, jamais par l'IP hôte `10.10.3.141`, hairpin bloqué).

## Modèle de graphe

**Aucun nœud routeur n'est créé** : chaque routeur BGP-LS est rattaché au nœud
équipement NetBox homonyme (match insensible à la casse sur `Nom`, résolution
`IgpRouterId`/`RouterId` -> `NodeName` reconstruite à chaque cycle depuis les
tables nœuds ClickHouse). Les routeurs sans nom ou absents de NetBox sont
ignorés (compteurs dans les logs). Les propriétés BGP posées sur les
équipements (`Asn`, `RouterId`, `IgpRouterId`, `Withdraw`, ...) sont volatiles
(netbox-neo4j-sync les réécrit) : l'état durable vit sur les relations.

**Nœuds**
- `(:Prefix {Key, Prefix, Family})` — `Key = "<Family>|<Prefix>"`. Seuls nœuds
  appartenant à cette synchro.

**Relations**
- `(équipement)-[:ISIS {Key, IgpMetric, Withdraw, ...}]->(équipement)`
  — adjacence IGP, depuis `bgp_ls_links` uniquement.
  `Key` = `LocalIgpRouterId|RemoteIgpRouterId` (les RouterId loopback sont
  parfois vides dans `bgp_ls_links`). Les événements `monitor_bgp_ls_link` ne
  créent jamais de lien : ils posent `Withdraw`/`LastEventAge` sur le lien
  existant, leurs RouterId étant résolus en IgpRouterId.
- `(équipement)-[:ANNOUNCES_PREFIX {Withdraw, ...}]->(:Prefix)` — réseau IGP
  atteignable depuis ce routeur (`bgp_ls_prefixV4/V6` / `SAFI_LINK_STATE_PREFIXE_V4/V6`).
- `(équipement)-[:ANNOUNCES_ROUTE {Family, AsPath, LocalPref, Withdraw, ...}]->(:Prefix)`
  — route BGP classique (`monitor_bgp_ipv4unicast`/`monitor_bgp_lu`/`monitor_bgp_vpn`),
  `Family` ∈ `ipv4unicast`/`labeled_unicast`/`vpn`. L'équipement est retrouvé
  via `OriginatorId` (= `RouterId` BGP-LS) -> `NodeName`. Si `OriginatorId` ne
  correspond à aucun équipement connu, la ligne est ignorée (voir logs du
  cycle monitor, compteur "ignorée(s)").

## Mise en route

```bash
cp .env.example .env      # puis renseigner CLICKHOUSE_PASSWORD / NEO4J_PASSWORD
docker compose build
docker compose up -d
docker compose logs -f reconciler
```

### Créer l'utilisateur ClickHouse en lecture seule

`gobgp_writer` (existant) a SELECT+INSERT, trop large pour ce service. Exécuter
une fois `lorion01vel/gobgp/schemas/01_reader_role.sql` contre `10.10.3.141`
(même procédure que `00_setup.sql`), puis reporter le mot de passe choisi dans
`secrets/ch_gobgp_reader_password` (chmod 600, hors git) et `.env`.

## Administration (CLI `python -m admin`)

```bash
docker compose run --rm reconciler python -m admin <commande>
```

| Commande | Rôle |
|----------|------|
| `stats` | Compteurs du graphe (nœuds par label, relations par type) |
| `init` | Full-sync immédiat (cycle topologie + cycle monitor) |
| `wipe [--yes]` | Purge les données de cette synchro : relations ISIS/ANNOUNCES_*, nœuds Prefix, propriétés BGP des équipements |

## Vérification

```bash
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (a)-[l:ISIS]->(b) RETURN a.Nom, b.Nom, l.IgpMetric, l.Withdraw LIMIT 10"

docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (n)-[:ANNOUNCES_PREFIX]->(p:Prefix) RETURN n.Nom, p.Prefix LIMIT 10"
```

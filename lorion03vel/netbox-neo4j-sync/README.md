# netbox-neo4j-sync

Synchronise les devices NetBox vers Neo4j selon un **modèle métier dénormalisé**.

- **Architecture** : `receiver` (webhooks NetBox, quasi temps réel) + `reconciler`
  (synchro complète périodique + purge). **Pas de RabbitMQ.**
- NetBox et Neo4j **ne sont pas gérés ici** : on s'y attache via le réseau
  Docker partagé de la VM (`lorion03vel-network`, external).

## Modèle de graphe

**Un nœud par device**, dont le **label est le rôle feuille** (`:spinebib`, `:pesms`,
...). Clé métier `Id` (= device.id), contrainte d'unicité par rôle. Propriétés
dénormalisées :

```
(:spinebib {
  Id, Nom, Role, Fonction, Manufacturer, Chassis, Site, Rack,
  Position, Face, Entite, LastUpdate,
  ConsolePorts:[...], Loopback123:"10.104.133.3/32"
})
```

| Propriété | Source NetBox |
|-----------|---------------|
| Role / Fonction | rôle feuille / rôle racine (hiérarchie des device-roles) |
| Manufacturer / Chassis | device_type.manufacturer.name / device_type.model |
| Site / Rack / Position / Face | device.site.id / rack.name / position / face.label |
| Entite | tenant.name |
| ConsolePorts | dcim/console-ports |
| Loopback* | IP (IPAM) des interfaces nommées `Loopback*` |

**Relation `(a)-[:EST_CONNECTE_A {…}]->(b)`** : une par câble entre deux devices, avec
`CableName, Source, Destination, LocalPortName, RemoteDevicePort, InterfaceId,
RemoteDeviceId, Lag, Status`.

## Mise en route

```bash
cp .env.example .env      # puis renseigner les valeurs (voir ci-dessous)
docker compose build
docker compose up -d
docker compose logs -f reconciler
```

### Variables `.env`

| Variable | Rôle |
|----------|------|
| `NETBOX_API_URL` | URL interne NetBox (`http://netbox:8080`) |
| `NETBOX_TOKEN` | **À créer** dans NetBox (Admin → API Tokens), lecture DCIM + IPAM |
| `WEBHOOK_SECRET` | Secret partagé avec le Webhook NetBox (signature HMAC-SHA512) |
| `NEO4J_URI/USER/PASSWORD` | Connexion Neo4j (`bolt://lorion03vel-neo4j:7687`) |
| `RECONCILE_INTERVAL_SECONDS` | Intervalle de synchro complète (défaut 900) |
| `BUILD_HTTP(S)_PROXY` | Proxy utilisé **uniquement** au build (pip/PyPI) |

> **Adresses conteneur vs hôte** — les services tournent **en conteneur**, sur le
> réseau Docker partagé `lorion03vel-network`. Les valeurs par
> défaut sont donc les **noms DNS internes** :
>
> | Variable | En conteneur (défaut) | Depuis l'hôte |
> |----------|-----------------------|---------------|
> | `NETBOX_API_URL` | `http://netbox:8080` | `http://localhost:9998` (port publié) |
> | `NEO4J_URI` | `bolt://lorion03vel-neo4j:7687` | `bolt://localhost:7687` (port publié) |
>
> `netbox` (port interne 8080) et `lorion03vel-neo4j` ne sont **résolubles que depuis
> les conteneurs du réseau**, pas depuis l'hôte. Ne surcharger par les valeurs `localhost`
> que si on lance le code **directement sur l'hôte** (hors `docker compose run`).

## Administration (CLI `python -m admin`)

Un CLI automatise la config NetBox et la gestion Neo4j. Il s'exécute via le service
reconciler (mêmes `.env` et réseaux) :

```bash
docker compose run --rm reconciler python -m admin <commande>
```

| Commande | Rôle |
|----------|------|
| `stats` | Compteurs du graphe (nœuds, EST_CONNECTE_A, labels/rôles) |
| `init` | Full-sync immédiat NetBox → Neo4j (bootstrap) |
| `wipe [--drop-constraints] [--yes]` | Purge le graphe (et contraintes si demandé) |
| `delete-device --id N` | Supprime le nœud device d'`Id` N |
| `setup-webhooks [--url U] [--name NAME]` | Crée/MAJ le Webhook + Event Rule NetBox (idempotent) |
| `teardown-webhooks [--name NAME]` | Supprime le Webhook + Event Rule |

## Configuration côté NetBox (temps réel)

1. **API Token** : Admin → API Tokens → créer un token → `NETBOX_TOKEN`.
2. **Webhook + Event Rule** : `docker compose run --rm reconciler python -m admin setup-webhooks`
   (crée un Webhook vers le receiver + une Event Rule sur Device/Interface/Console
   Port/IP Address/Cable/Device Role pour create/update/delete). Le secret utilisé
   est `WEBHOOK_SECRET`.

NetBox 4.x envoie `object_type` (ex. `dcim.device`) et signe le corps en HMAC-SHA512.
Sans Event Rule, seul le `reconciler` synchronise (toutes les N minutes).

## Vérification

```bash
# Labels = rôles
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "CALL db.labels() YIELD label RETURN label ORDER BY label"

# Un device et ses propriétés
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (d {Id:122}) RETURN labels(d), d.Nom, d.Role, d.Fonction, d.Loopback123"

# Câblage device <-> device
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (a {Id:122})-[r:EST_CONNECTE_A]-(b) RETURN r.CableName, r.Source, r.Destination, r.Lag LIMIT 5"
```

## Fonctionnement interne

- `common/mapping.py` : **source unique** du mapping NetBox → graphe (réutilisée par
  le receiver et le reconciler) : `device_props`, `cable_rel`, dispatch webhook.
- `common/neo4j_client.py` : upsert idempotent (`MERGE`), purge ; labels de rôle
  validés/back-quotés (anti-injection).
- Le receiver resynchronise le device concerné en ré-interrogeant NetBox (modèle
  dénormalisé) ; le reconciler rattrape les changements « larges » (rename site/rôle).

## Hors périmètre (extensible via `mapping.py`)

Champ `New` (pas de source NetBox). VLAN/VRF, virtualisation, circuits.

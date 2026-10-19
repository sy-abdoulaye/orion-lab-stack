# Infrastructure

## VMs du lab

La plateforme est répartie sur **plusieurs VM** du lab (Backbone Solutions / Validation),
une stack Compose par VM :

| VM | Rôle | Dépôt | Stack |
|----|------|-------|-------|
| `lorion01vel` | Collecte BGP-LS | `/data/orion-lab-stack` | gobgp, vector |
| `lorion02vel` | NetBox (instance dédiée) — gnmic prévu | *(à provisionner)* | netbox-docker (NetBox, worker, PostgreSQL, Redis ×2) |
| `lorion03vel` | Stockage & enrichissement | `~/autoCOREBIB/orion-lab-stack` | Neo4j, ClickHouse, syncs, docs |

| Élément commun | Valeur |
|----------------|--------|
| OS | Linux (noyau 5.15) |
| Runtime | Docker + Docker Compose v2 |
| Déploiement NetBox | `/home/services/netbox-docker` sur lorion03vel (hors dépôt) |
| Déploiement multi-VM | `make deploy VM=…` depuis le poste d'admin (`deploy/deploy.sh`, SSH+rsync) |

## Isolation Internet & proxy

!!! warning "Les conteneurs n'ont pas d'accès Internet"
    Dans ce lab, **aucun conteneur** n'a d'accès sortant vers Internet — ni en direct, ni
    via le proxy. Seul l'**hôte** dispose d'un accès, via le proxy d'entreprise
    `http://<https_proxy_addr>:<port>`. Le proxy lui-même est **injoignable depuis un conteneur**
    (bloqué par routage/pare-feu). La résolution DNS fonctionne, mais aucune route sortante
    n'existe depuis les conteneurs.

Conséquences concrètes, réellement rencontrées et gérées dans le projet :

| Besoin | Impossible dans un conteneur | Solution appliquée |
|--------|------------------------------|--------------------|
| Plugins Neo4j (APOC, GDS) | `NEO4J_PLUGINS` télécharge depuis le conteneur | JARs téléchargés **sur l'hôte** (via proxy) puis montés (`neo4j/plugins/`) |
| Dépendances Python (pip) | `pip install` pendant `docker build` | Proxy passé en **build-arg** (`BUILD_HTTP(S)_PROXY`) — pip via proxy uniquement au build |
| Images Docker | `docker pull` depuis Docker Hub | Miroir interne `registry.example.com/dockerhub/…` |

## Miroir d'images

Toutes les images proviennent du miroir interne, jamais de `docker.io` directement. Le préfixe
du registre est **paramétré** dans les `compose.yml`
(`${REGISTRY:-registry.example.com/dockerhub}`) : une seule variable à changer si le miroir
évolue. Deux conventions de nommage coexistent, lisibles dans `docker ps` :

- **`registry.example.com/dockerhub/…`** = image officielle tirée du miroir, non modifiée ;
- **`orion/<service>:<tag>`** = image buildée dans ce dépôt (tag via `IMAGE_TAG`, bump = rollback possible).

| Service | Image réelle |
|---------|--------------|
| Neo4j | `${REGISTRY}/neo4j:5.26.0` |
| ClickHouse | `${REGISTRY}/clickhouse/clickhouse-server:25.6-alpine` |
| netbox-neo4j-sync | `orion/netbox-neo4j-sync-*:0.1.0` (build local sur `${REGISTRY}/library/python:3.12-slim`) |
| gobgp-neo4j-sync | `orion/gobgp-neo4j-sync-reconciler:0.1.0` (build local sur `${REGISTRY}/library/python:3.12-slim`) |
| NetBox | `${REGISTRY}/netboxcommunity/netbox:v4.5.4-4.0.1` (image locale `-plugins`) |
| PostgreSQL | `${REGISTRY}/postgres:17-alpine` |
| Redis/Valkey | `${REGISTRY}/valkey/valkey:8.1-alpine` |

!!! tip "Vérifier l'accès (extrait de `lorion03vel/cmd.md`)"
    ```bash
    # Depuis un conteneur : Internet bloqué
    docker exec lorion03vel-neo4j sh -c \
      'curl -sI -m 10 https://github.com >/dev/null 2>&1 && echo ACCESSIBLE || echo BLOQUE'

    # Depuis l'hôte : accès via proxy
    curl -sI -m 10 https://github.com >/dev/null 2>&1 && echo ACCESSIBLE || echo BLOQUE
    env | grep -i proxy
    ```

## Organisation du dépôt

```text
orion-lab-stack/
├── Makefile                        # pilotage multi-VM (deploy/down/status)
├── common.mk                       # cibles make partagées par les VMs
├── deploy/                         # deploy.sh, hosts.env, unit systemd
├── lorion01vel/
│   ├── docker-compose.yml          # projet "lorion01vel" (include)
│   ├── Makefile                    # NET := lorion01vel-network + common.mk
│   ├── gobgp/                      # daemon BGP-LS + client CLI (CSV)
│   └── vector/                     # expédition CSV -> ClickHouse
├── lorion02vel/
│   ├── docker-compose.yml          # projet "lorion02vel" (include)
│   ├── Makefile                    # NET := lorion02vel-network + common.mk
│   └── netbox-docker/              # clone netbox-docker + override local (gnmic prévu en plus)
├── lorion03vel/
│   ├── docker-compose.yml          # projet "lorion03vel" (include)
│   ├── Makefile                    # NET := lorion03vel-network + common.mk
│   ├── cmd.md                      # aide-mémoire de commandes
│   ├── neo4j/                      # service Neo4j
│   ├── clickhouse/                 # service ClickHouse (base gobgp)
│   ├── netbox-neo4j-sync/          # sync NetBox -> Neo4j
│   └── gobgp-neo4j-sync/           # sync ClickHouse (BGP-LS) -> Neo4j
└── orion-stack-documentation/      # ce portail (mkdocs -> nginx :8090)
```

!!! note
    Le répertoire `lorion02vel/` est réservé (collecte gnmic prévue), non provisionné
    à ce jour.

## Ressources & limites réellement configurées

- **Neo4j** : `ulimits.nofile` 262144 ; mémoire heap 2–3 Go, page cache 6 Go
  (voir [Neo4j / Configuration](../services/neo4j/configuration.md)).
- **ClickHouse** : `ulimits.nofile` 262144 (voir [ClickHouse / Configuration](../services/clickhouse/configuration.md)).
- **netbox-neo4j-sync** : pas de limite explicite ; le reconciler est prévu pour être
  répliqué horizontalement si besoin.

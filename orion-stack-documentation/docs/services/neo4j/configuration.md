# Neo4j — Configuration

Toute la configuration provient de `lorion03vel/neo4j/compose.yml` et `lorion03vel/neo4j/.env`.

## Variables d'environnement (`neo4j/.env`)

| Variable | Valeur réelle | Rôle |
|----------|---------------|------|
| `NEO4J_CONTAINER` | `lorion03vel-neo4j` | Nom du conteneur |
| `IMAGE_NEO4J` | `neo4j:5.26.0` | Tag d'image (préfixé par le miroir dans le compose) |
| `NEO4J_AUTH_FILE` | `/run/secrets/neo4j_auth` | Fichier secret `user/password` lu au 1er démarrage |
| `TZ` | `Europe/Paris` | Fuseau horaire |
| `NEO4J_dbms_security_procedures_unrestricted` | `apoc.*,gds.*` | Procédures non restreintes |
| `NEO4J_dbms_security_procedures_allowlist` | `apoc.*,gds.*` | Liste blanche des procédures |
| `NEO4J_server_memory_pagecache_size` | `6G` | Cache de pages |
| `NEO4J_server_memory_heap_initial__size` | `2G` | Heap JVM initial |
| `NEO4J_server_memory_heap_max__size` | `3G` | Heap JVM max |

!!! note "Convention de nommage des variables Neo4j"
    L'image Neo4j convertit les variables `NEO4J_xxx` en paramètres `neo4j.conf` :
    le `_` devient `.` et le `__` devient `_`. Ainsi
    `NEO4J_server_memory_heap_max__size` → `server.memory.heap.max_size`. Ces clés utilisent
    la nomenclature **Neo4j 5.x** (`server.memory.*`), qui remplace l'ancienne `dbms.memory.*`.

## Image (interpolation)

```yaml
image: registry.example.com/dockerhub/${IMAGE_NEO4J:-neo4j:5.26.0}
```

L'image finale est `registry.example.com/dockerhub/neo4j:5.26.0`.

## Extrait du service (`neo4j/compose.yml`)

```yaml
services:
  neo4j:
    image: registry.example.com/dockerhub/${IMAGE_NEO4J:-neo4j:5.26.0}
    container_name: ${NEO4J_CONTAINER:-lorion03vel-neo4j}
    restart: unless-stopped
    environment:
      NEO4J_AUTH_FILE: ${NEO4J_AUTH_FILE:-/run/secrets/neo4j_auth}
      NEO4J_dbms_security_procedures_unrestricted: ${NEO4J_dbms_security_procedures_unrestricted:-apoc.*,gds.*}
      NEO4J_dbms_security_procedures_allowlist: ${NEO4J_dbms_security_procedures_allowlist:-apoc.*,gds.*}
      NEO4J_server_memory_pagecache_size: ${NEO4J_server_memory_pagecache_size:-512M}
      # ...
    ports: ["7474:7474", "7687:7687"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/import
      - ./plugins:/plugins
    ulimits:
      nofile: { soft: 262144, hard: 262144 }
    networks: [lorion03vel-network]
    secrets: [neo4j_auth]
```

## Fichiers de configuration

- Pas de `neo4j.conf` custom monté : la configuration passe **exclusivement** par les
  variables `NEO4J_*`. (Le montage `./config/neo4j.conf` est présent mais **commenté**.)
- Les **plugins** sont fournis via le bind `./plugins:/plugins`.

## Gestion des secrets

Le mot de passe n'apparaît nulle part en clair. Il est fourni via un **Docker secret** :

```yaml
secrets:
  neo4j_auth:
    file: ./secrets/neo4j_auth   # contenu : neo4j/<motdepasse>
```

Monté dans le conteneur sur `/run/secrets/neo4j_auth`, il est lu au **premier démarrage** via
`NEO4J_AUTH_FILE` pour initialiser le compte `neo4j`. Voir [Sécurité](security.md).

## Paramètres mémoire

| Paramètre | Valeur | Effet |
|-----------|--------|-------|
| `server.memory.pagecache.size` | 6 Go | Cache des données/index en mémoire |
| `server.memory.heap.initial_size` | 2 Go | Heap JVM au démarrage |
| `server.memory.heap.max_size` | 3 Go | Plafond heap JVM |

!!! tip "Dimensionnement"
    Ces valeurs sont à adapter à la RAM de l'hôte et à la taille du graphe. Le page cache doit
    idéalement contenir les données « chaudes » ; le heap sert au traitement des requêtes.

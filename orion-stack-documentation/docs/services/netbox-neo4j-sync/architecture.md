# netbox-neo4j-sync — Architecture

## Composants & modules

```mermaid
flowchart TB
    subgraph common["common/ (cœur partagé)"]
        CFG["config.py\n(Settings depuis env)"]
        LOG["logging.py"]
        NBC["netbox_client.py\n(httpx)"]
        NEC["neo4j_client.py\n(driver bolt)"]
        MAP["mapping.py\n(règles NetBox->graphe)"]
    end
    subgraph receiver["receiver/"]
        APP["app.py (FastAPI)"]
    end
    subgraph reconciler["reconciler/"]
        MAIN["main.py (boucle)"]
    end
    subgraph admin["admin/"]
        CLI["__main__.py (CLI)"]
    end
    APP --> MAP & NBC & NEC
    MAIN --> MAP & NBC & NEC
    CLI --> MAP & NBC & NEC
    MAP --> NBC & NEC
```

!!! abstract "Principe : une source de vérité pour le mapping"
    `common/mapping.py` centralise la traduction NetBox → graphe (nœuds & relations). Il est
    **réutilisé à l'identique** par le receiver (1 objet), le reconciler (balayage complet) et le
    CLI. Un seul endroit à maintenir.

## Conteneurs & ports

| Conteneur | Rôle | Port | Réseaux |
|-----------|------|------|---------|
| `netbox-neo4j-sync-receiver` | FastAPI (webhooks) | 8000 (non publié) | `lorion03vel-network` |
| `netbox-neo4j-sync-reconciler` | Boucle de sync | — | `lorion03vel-network` |

Les deux images sont **construites localement** à partir de
`registry.example.com/dockerhub/library/python:3.12-slim` (voir [Déploiement](deployment.md)).

## Communications

```mermaid
sequenceDiagram
    participant NB as NetBox
    participant RCV as receiver
    participant REC as reconciler
    participant NEO as Neo4j

    NB->>RCV: POST /webhook (HMAC)
    RCV->>NB: GET /api/... (resync device)
    RCV->>NEO: MERGE (Bolt 7687)
    loop toutes les N s
        REC->>NB: GET /api/... (balayage complet)
        REC->>NEO: MERGE + purge
    end
```

| Flux | Protocole | Détail |
|------|-----------|--------|
| NetBox → receiver | HTTP `:8000` | Webhooks signés HMAC-SHA512 |
| receiver/reconciler → NetBox | HTTP `:8080` | Lecture API REST (token) |
| receiver/reconciler → Neo4j | Bolt `:7687` | Écritures Cypher (`MERGE`) |

## Dépendances Python (`requirements.txt`)

| Paquet | Usage |
|--------|-------|
| `fastapi`, `uvicorn[standard]` | Receiver HTTP |
| `httpx` | Client API NetBox |
| `neo4j` | Driver Bolt |
| `tenacity` | Retries sur erreurs transitoires |
| `python-dotenv` | Chargement `.env` en développement |

## Résilience

- **Retries** (`tenacity`) sur les erreurs réseau transitoires (NetBox HTTP, Neo4j Bolt).
- **Arrêt gracieux** du reconciler (SIGTERM/SIGINT → fin du cycle en cours).
- Le reconciler **capture** les exceptions d'un cycle et **retente** au cycle suivant (ne meurt
  pas sur une erreur ponctuelle).

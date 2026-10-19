# orion-stack-documentation

Documentation d'entreprise de la plateforme **Orion** (`orion-lab-stack/lorion03vel`),
construite avec [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) et
organisée **par service**.

> **Principe** : cette documentation ne décrit que l'implémentation **réelle** du projet
> (fichiers `compose`, `Dockerfile`, `.env`, XML, scripts, code). Aucune configuration
> n'est inventée. Les services planifiés mais non déployés sont regroupés dans la page
> [Roadmap](docs/architecture/roadmap.md).

## Périmètre documenté

| Service | Statut | Rôle |
|---------|--------|------|
| **Neo4j** | Actif | Base de données orientée graphe (APOC + GDS) |
| **ClickHouse** | Actif | Base analytique OLAP (base `gobgp`, alimentée depuis lorion01vel) |
| **netbox-neo4j-sync** | Actif | Synchronisation NetBox → Neo4j (receiver FastAPI + reconciler + CLI) |
| **gobgp-neo4j-sync** | Actif | Synchronisation ClickHouse (BGP-LS) → Neo4j (reconciler) |
| **NetBox** (+ PostgreSQL, Redis/Valkey, worker) | Actif (externe) | Source de vérité DCIM |

## Prérequis

- Python 3.10+
- Accès à Internet (ou proxy) pour installer les dépendances.

## Installation & prévisualisation

```bash
cd orion-stack-documentation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

mkdocs serve          # prévisualisation sur http://127.0.0.1:8000
mkdocs build --strict # génération statique dans ./site (échoue sur lien cassé)
```

## Déploiement conteneurisé (accès depuis l'IP de l'hôte)

La documentation est servie par un conteneur **nginx** (site statique construit par MkDocs lors
du build de l'image). Elle est publiée sur le **port 8090** de l'hôte.

```bash
cd orion-stack-documentation
cp .env.example .env            # proxy de build (pip) — non secret
docker compose up -d --build    # construit le site puis lance nginx
```

Accès : **`http://<IP_HOTE>:8090`** (ex. `http://10.66.4.161:8090`).

| Action | Commande |
|--------|----------|
| Démarrer / reconstruire | `docker compose up -d --build` |
| État | `docker compose ps` |
| Logs nginx | `docker compose logs -f docs` |
| Arrêter | `docker compose down` |

!!! note
    Le proxy (`BUILD_HTTP_PROXY` / `BUILD_HTTPS_PROXY` dans `.env`) n'est utilisé **qu'au build**
    (installation de `mkdocs-material`). Le conteneur nginx final ne nécessite aucun accès Internet.

Le port hôte est configurable dans `compose.yml` (`ports: ["8090:80"]`).

### Optimisations « 100 % hors-ligne » (chargement rapide)

Le navigateur du poste client n'ayant pas forcément accès à Internet, toute ressource externe
ralentit (voire bloque) le rendu. Le site est donc **entièrement auto-porté** :

- `theme.font: false` — pas de **Google Fonts** (police système, pas de fetch bloquant).
- **Mermaid hébergé en local** (`docs/assets/js/mermaid.min.js`) — Material détecte le global
  `mermaid` et n'appelle **pas** le CDN unpkg.
- `navigation.instant` **+ `site_url`** — navigation type SPA (pas de rechargement complet).
  `site_url` est requis par Material pour activer le chargement instantané.
- **gzip** + en-têtes de cache côté nginx (`nginx-default.conf`) — ex. `mermaid.min.js` 3,4 Mo
  → ~1 Mo ; HTML en `no-cache` (jamais périmé), assets hashés en cache long.

!!! tip "Mettre à jour Mermaid"
    ```bash
    curl -sL -o docs/assets/js/mermaid.min.js https://unpkg.com/mermaid@11/dist/mermaid.min.js
    docker compose up -d --build
    ```

### Build ponctuel du site (sans conteneur nginx)

Le lab n'a pas d'accès Internet direct depuis les conteneurs : le proxy est passé en variable.

```bash
docker run --rm -v "$PWD":/d -w /d \
  -e http_proxy=http://<http-proxy>:<port> -e https_proxy=http://<http-proxy>:<port> \
  hub.valentine.sfr.com/dockerhub/library/python:3.12-slim \
  sh -c "pip install -r requirements.txt && mkdocs build --strict"
```

## Organisation

```text
docs/
├── index.md              # Portail d'accueil
├── architecture/         # Vues transverses (infra, réseau, sécurité, flux, roadmap)
├── services/             # Un dossier par service
│   ├── neo4j/
│   ├── clickhouse/
│   ├── netbox-neo4j-sync/
│   └── netbox/
├── operations/           # Déploiement, sauvegarde, MAJ, runbook
├── monitoring/
├── troubleshooting/
└── faq/
```

## Contribution

Pour documenter un nouveau service (ex. Kafka, Traefik — cf. Roadmap), créer un dossier
`docs/services/<service>/` en suivant le modèle à 8 pages (`index`, `architecture`,
`configuration`, `security`, `deployment`, `maintenance`, `monitoring`, `troubleshooting`)
et l'ajouter à la section `nav` de `mkdocs.yml`. **N'y documenter que ce qui existe
réellement dans le dépôt.**

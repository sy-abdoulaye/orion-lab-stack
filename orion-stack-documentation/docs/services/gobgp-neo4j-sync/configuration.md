# gobgp-neo4j-sync — Configuration

Configuration **12-factor** : tout vient des variables d'environnement (injectées par
`env_file: .env` dans le compose ; `python-dotenv` permet aussi un `.env` local en
développement). Un objet `settings` unique (`common/config.py`) est partagé par le
reconciler et le CLI.

## Variables

| Variable | Défaut | Rôle |
|----------|--------|------|
| `CLICKHOUSE_HOST` | `10.10.3.141` | **À surcharger** : `lorion03vel-clickhouse` (conteneur local, jamais l'IP hôte) |
| `CLICKHOUSE_PORT` | `9000` | Protocole **natif** (le HTTP casse avec le proxy d'entreprise) |
| `CLICKHOUSE_USER` | `gobgp_reader` | Utilisateur **lecture seule** (`01_reader_role.sql`) |
| `CLICKHOUSE_PASSWORD_FILE` | `/run/secrets/ch_gobgp_reader_password` | Fichier secret monté (compose `secrets:`) |
| `CLICKHOUSE_DATABASE` | `gobgp` | Base alimentée par la collecte |
| `NEO4J_URI` | `bolt://lorion03vel-neo4j:7687` | Cible graphe |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD_FILE` | `/run/secrets/neo4j_password` | Fichier secret monté (= partie après `/` de `neo4j/secrets/neo4j_auth`) |
| `RECONCILE_INTERVAL_SECONDS` | `300` | Période du cycle **topologie** |
| `MONITOR_POLL_INTERVAL_SECONDS` | `20` | Période du cycle **monitor** |
| `MONITOR_WINDOW_SECONDS` | `120` | Fenêtre glissante lue par le monitor — **doit rester > intervalle** pour couvrir un cycle en retard |
| `LOG_LEVEL` | `INFO` | |
| `BUILD_HTTP_PROXY` / `BUILD_HTTPS_PROXY` | *(vide)* | **Build uniquement** (pip/PyPI) — pas utilisés à l'exécution |

## Dimensionnement des intervalles

!!! tip "Comment régler les trois périodes"
    - `RECONCILE_INTERVAL_SECONDS` : coût d'un cycle = lecture complète des tables
      d'état + purge. 300 s est adapté au volume actuel (~600 annonces, ~100 liens).
    - `MONITOR_POLL_INTERVAL_SECONDS` : latence maximale d'un `Withdraw` dans le graphe.
    - `MONITOR_WINDOW_SECONDS` : garder **≥ 2×** l'intervalle. Les écritures étant
      idempotentes, une fenêtre large ne crée pas de doublon — elle coûte juste un peu
      de lecture.

## Gestion des secrets

Les deux secrets vivent dans **`secrets/`** (`chmod 600`, exclus de git), montés par le
compose et lus via `*_FILE` (`common/config.py`, `_env_or_file`) — le `.env` ne contient
que du non-sensible et est **versionné** :

| Fichier | Contenu |
|---------|---------|
| `secrets/ch_gobgp_reader_password` | mot de passe `gobgp_reader` (cf. `01_reader_role.sql`) |
| `secrets/neo4j_password` | mot de passe Neo4j |

!!! warning "Écrire les fichiers sans guillemets ni fin de ligne"
    `printf '%s' '<valeur>' > secrets/<nom>` — des guillemets **dans** le fichier
    seraient envoyés tels quels au serveur (authentification refusée). Après
    modification d'un secret, **recréer** le conteneur (`--force-recreate`) : le
    montage pointe sur l'inode du fichier.

## Exemple de `.env`

Voir `.env.example` (commenté). Points de vigilance :

```bash
CLICKHOUSE_HOST=lorion03vel-clickhouse   # nom Docker, PAS 10.10.3.141 (hairpin)
CLICKHOUSE_USER=gobgp_reader             # lecture seule, PAS gobgp_writer
```

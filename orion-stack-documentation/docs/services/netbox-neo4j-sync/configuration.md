# netbox-neo4j-sync — Configuration

Configuration via `netbox-neo4j-sync/.env` (gabarit : `.env.example`) pour le
non-sensible, et via des **fichiers `secrets/`** pour les secrets. Lue par
`common/config.py`.

## Variables d'environnement

| Variable | Exemple / défaut | Rôle |
|----------|------------------|------|
| `NETBOX_API_URL` | `http://netbox:8080` | URL **interne** de l'API NetBox |
| `NETBOX_TOKEN_FILE` | `/run/secrets/netbox_token` | Fichier contenant le token API NetBox (lecture DCIM + IPAM) |
| `NETBOX_VERIFY_SSL` | `false` | Vérification TLS (NetBox en HTTP interne) |
| `WEBHOOK_SECRET_FILE` | `/run/secrets/webhook_secret` | Fichier contenant le secret HMAC partagé avec le Webhook NetBox |
| `NEO4J_URI` | `bolt://lorion03vel-neo4j:7687` | URI Bolt Neo4j |
| `NEO4J_USER` | `neo4j` | Utilisateur Neo4j |
| `NEO4J_PASSWORD_FILE` | `/run/secrets/neo4j_password` | Fichier contenant le mot de passe Neo4j |
| `RECONCILE_INTERVAL_SECONDS` | `900` | Intervalle de synchro complète |
| `SITE_NOM` | `782061` | Nom du nœud `:SITE` (référentiel interne) auquel les devices sont rattachés (`EST_HEBERGE_DANS`) |
| `LOG_LEVEL` | `INFO` | Niveau de log |
| `BUILD_HTTP_PROXY` / `BUILD_HTTPS_PROXY` | proxy | **Build uniquement** (pip via proxy) |

!!! warning "Adresses conteneur vs hôte"
    Les valeurs par défaut sont les **noms DNS internes** (résolus depuis les conteneurs).

    | Variable | En conteneur | Depuis l'hôte |
    |----------|--------------|---------------|
    | `NETBOX_API_URL` | `http://netbox:8080` | `http://localhost:9999` |
    | `NEO4J_URI` | `bolt://lorion03vel-neo4j:7687` | `bolt://localhost:7687` |

## Fichiers

- `.env` : configuration non sensible (**versionnée** — aucun secret dedans).
- `.env.example` : gabarit commenté.
- `secrets/` : un fichier par secret, `chmod 600`, **exclu de git** (`**/secrets/`).
- `requirements.txt` : dépendances Python.

## Gestion des secrets

Trois fichiers dans `secrets/`, montés par le compose (`secrets:`) et lus via `*_FILE` :

| Fichier | Contenu | Alignement |
|---------|---------|------------|
| `secrets/netbox_token` | Token API | Créé dans NetBox (Admin → API Tokens) |
| `secrets/webhook_secret` | Secret HMAC | **Identique** au champ `secret` du Webhook NetBox (sinon 401) |
| `secrets/neo4j_password` | Mot de passe Neo4j | = partie après `/` de `neo4j/secrets/neo4j_auth` |

!!! warning "Un seul contenu, pas de fin de ligne parasite"
    Écrire les fichiers avec `printf '%s' '<valeur>' > secrets/<nom>` (pas d'`echo`,
    pas de guillemets dans le fichier). Le code fait un `.strip()`, mais des guillemets
    **dans** le fichier seraient envoyés tels quels à NetBox (→ 403).

Générer un secret fort :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Après changement de `secrets/webhook_secret`, relancer `admin setup-webhooks` et
**recréer** les conteneurs (`docker compose up -d --force-recreate receiver reconciler`
— le montage pointe sur l'inode du fichier).

## Configuration côté NetBox

Deux mécanismes possibles :

=== "Automatique (recommandé)"

    ```bash
    docker compose run --rm reconciler python -m admin setup-webhooks
    ```

=== "Manuel"

    1. **API Token** : Admin → API Tokens.
    2. **Webhook** : `payload_url = http://netbox-neo4j-sync-receiver:8000/webhook`, secret =
       `WEBHOOK_SECRET`, méthode POST.
    3. **Event Rule** : objets Device / Interface / Console Port / IP Address / Cable / Device
       Role, événements create/update/delete → ce Webhook.

# Neo4j — Sécurité

## Gestion des secrets

Le mot de passe du compte `neo4j` est stocké dans un **Docker secret**, jamais en clair :

```yaml
secrets:
  neo4j_auth:
    file: ./secrets/neo4j_auth
```

- Contenu du fichier : `neo4j/<motdepasse>` (format attendu par `NEO4J_AUTH` / `NEO4J_AUTH_FILE`).
- Monté dans le conteneur sur `/run/secrets/neo4j_auth`.
- Le dossier `neo4j/secrets/` est exclu du versionnement.

!!! warning "Droits de lecture du secret"
    Le processus Neo4j tourne sous l'utilisateur `neo4j` (uid 7474) dans le conteneur. Le
    fichier secret doit être **lisible** par cet utilisateur (le montage direct et des droits
    adéquats sur l'hôte le permettent). Un secret illisible provoque au démarrage :
    `The secret file '/run/secrets/neo4j_auth' does not exist or is not readable`.

## Authentification

- Compte unique **`neo4j`** (édition Community — un seul utilisateur).
- Le mot de passe est fixé au **premier démarrage** à partir du secret, puis persistant dans
  le volume `neo4j_data`.

!!! note "Format `NEO4J_AUTH`"
    NetBox/Neo4j Community n'accepte que l'utilisateur **`neo4j`**. Le fichier secret doit donc
    commencer par `neo4j/…`. Un autre nom d'utilisateur est refusé.

## Autorisation

- Édition **Community** : pas de RBAC multi-utilisateurs ni de rôles (fonctionnalités
  réservées à l'édition Enterprise).
- **Procédures** : seules `apoc.*` et `gds.*` sont autorisées via
  `dbms.security.procedures.allowlist` / `unrestricted`.

## TLS

!!! warning "Pas de TLS"
    Aucun certificat n'est configuré. Le port HTTPS 7473 est exposé par l'image mais **non
    utilisé**. Les connexions Bolt/HTTP se font en clair sur le réseau Docker interne.

## Reverse proxy

Aucun. Neo4j expose directement 7474/7687 sur l'hôte.

## Isolation Docker

- Attaché au seul réseau `lorion03vel-network`.
- Aucun accès Internet sortant.
- `restart: unless-stopped` pour la résilience.

## Licence Enterprise vs Community

!!! info "Choix Community assumé"
    L'édition **Enterprise** exige l'acceptation d'une licence
    (`NEO4J_ACCEPT_LICENSE_AGREEMENT`). En l'absence de licence, la plateforme utilise
    l'édition **Community** (`neo4j:5.26.0`, sans suffixe `-enterprise`), ce qui implique les
    limites ci-dessus (mono-utilisateur, pas de clustering/RBAC).

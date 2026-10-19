# netbox-neo4j-sync — Sécurité

## Authentification des flux

| Flux | Mécanisme |
|------|-----------|
| NetBox → receiver (webhooks) | **HMAC-SHA512** (`X-Hook-Signature`) vérifié à chaque appel |
| receiver/reconciler → NetBox | **Token API** (`Authorization: Token …`) |
| receiver/reconciler → Neo4j | **Utilisateur/mot de passe** Bolt |

## Signature des webhooks (HMAC)

`WEBHOOK_SECRET` est le **seul contrôle d'accès** sur l'endpoint `/webhook` :

- NetBox signe le corps avec le secret ; le receiver recalcule et compare en temps constant.
- Signature invalide → **401**, aucun traitement.

!!! danger "Importance du secret"
    Le receiver **écrit et supprime** dans Neo4j selon le contenu du webhook. Sans secret fort,
    un tiers pouvant joindre l'endpoint pourrait forger un `deleted` et supprimer des nœuds.
    Un `WEBHOOK_SECRET` **vide désactive** la vérification (le receiver accepte tout).

## Gestion des secrets

- Les trois secrets (`NETBOX_TOKEN`, `WEBHOOK_SECRET`, `NEO4J_PASSWORD`) vivent dans des
  **fichiers dédiés** `secrets/` (`chmod 600`, exclus de git via `**/secrets/`), montés
  dans les conteneurs par le mécanisme `secrets:` du compose et lus via les variables
  **`*_FILE`** (`NETBOX_TOKEN_FILE`, …) — voir `common/config.py` (`_env_or_file`).
- Le `.env` ne contient **que de la configuration non sensible** : il est **versionné**
  dans git sans risque.
- Aucun secret n'est écrit en clair dans le code, les images ou l'environnement des
  conteneurs (seuls les chemins `*_FILE` apparaissent dans `env`).

!!! danger "Rotation nécessaire (historique git)"
    Avant la mise en place de ce mécanisme, le `.env` **avec les trois secrets** a été
    committé : les valeurs restent lisibles dans l'**historique git**. Il faut les
    **faire tourner** : régénérer le token NetBox, changer `WEBHOOK_SECRET` (puis
    `setup-webhooks`), changer le mot de passe Neo4j — et reporter les nouvelles valeurs
    dans `secrets/`.

## Surface d'exposition

- Le receiver **n'est pas publié** sur l'hôte : joignable uniquement via le réseau
  `lorion03vel-network` (par NetBox). Cela limite fortement l'exposition.
- Le reconciler n'expose aucun port.

## Robustesse & anti-injection

- Les **labels de rôle** (dynamiques) sont validés/back-quotés avant interpolation Cypher
  (rejet de tout backtick) — pas d'injection via un nom de rôle.
- Les valeurs (`Id`, propriétés) sont toujours passées en **paramètres** Cypher.

## TLS

!!! warning "HTTP en clair (réseau interne)"
    Les échanges NetBox↔receiver et vers Neo4j se font en clair sur les réseaux Docker internes.
    `NETBOX_VERIFY_SSL=false` (NetBox en HTTP interne). Pas de TLS de plateforme (cf.
    [Roadmap](../../architecture/roadmap.md)).

## Bonnes pratiques

!!! tip
    - Définir un `WEBHOOK_SECRET` fort et le propager via `setup-webhooks`.
    - Restreindre le token NetBox aux droits **lecture** DCIM + IPAM.
    - Ne pas publier le port du receiver au-delà du réseau de confiance.

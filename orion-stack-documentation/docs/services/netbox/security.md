# NetBox — Sécurité

!!! info "Périmètre"
    NetBox étant géré par le projet externe `netbox-docker`, cette page couvre les aspects de
    sécurité **pertinents pour l'intégration** et ceux observés dans le déploiement.

## Authentification & accès

| Vecteur | Mécanisme |
|---------|-----------|
| UI / API | Authentification NetBox (session, tokens API) |
| API pour le sync | **Token API** dédié (`Authorization: Token …`) |
| Webhooks sortants | **Signature HMAC-SHA512** (champ `secret` du Webhook) |
| Base de données | Mot de passe PostgreSQL (`DB_PASSWORD`) |
| Redis | Mot de passe (`--requirepass`) sur les deux instances |

!!! tip "Principe du moindre privilège"
    Le token utilisé par `netbox-neo4j-sync` peut être restreint en **lecture** sur DCIM + IPAM
    (le sync ne modifie pas NetBox). La configuration des webhooks nécessite en revanche des
    droits d'écriture sur `extras` — à réserver à l'opération `setup-webhooks`.

## Secrets

- Les mots de passe vivent dans les fichiers `env/*.env` du projet netbox-docker (non
  committés ; des `.example` servent de gabarit).
- Le `secret` du Webhook doit être **identique** à `WEBHOOK_SECRET` côté sync.

## Réseau & exposition

- NetBox est publié sur l'hôte en **`9999`** (HTTP). PostgreSQL et Redis restent **internes**.
- Le worker désactive le proxy (`NO_PROXY="*"`) pour joindre le receiver en interne.

## TLS

!!! warning "HTTP (pas de TLS de plateforme)"
    L'accès à NetBox se fait en HTTP sur `9999`. Le sync utilise `NETBOX_VERIFY_SSL=false`
    (NetBox en HTTP interne). La terminaison TLS/reverse proxy est un chantier de la
    [Roadmap](../../architecture/roadmap.md).

## Bonnes pratiques d'intégration

!!! tip
    - Créer un **token dédié** au sync (révocable indépendamment).
    - Utiliser un `WEBHOOK_SECRET` **fort** et le faire tourner via `setup-webhooks`.
    - Supprimer les anciens Webhooks/Event Rules pointant vers des endpoints obsolètes
      (`admin teardown-webhooks`).

# Sécurité (vue globale)

Cette page décrit l'**état de sécurité réel** de la plateforme. Elle distingue clairement ce
qui est **mis en place** de ce qui ne l'est **pas encore**, sans rien présumer.

## Gestion des secrets

Aucun mot de passe n'est stocké en clair dans les fichiers de configuration versionnés. Deux
mécanismes coexistent selon le service :

| Service | Mécanisme | Détails |
|---------|-----------|---------|
| Neo4j | **Docker secret** (fichier) | `neo4j/secrets/neo4j_auth` (contenu `neo4j/<mdp>`), monté sur `/run/secrets/neo4j_auth`, lu via `NEO4J_AUTH_FILE` |
| ClickHouse | **Docker secret** + XML chiffré | `clickhouse/secrets/*` (montés), mots de passe en `password_sha256_hex` dans `users.d/*.xml` |
| netbox-neo4j-sync | **Docker secrets** (fichiers) + `*_FILE` | `secrets/netbox_token`, `secrets/webhook_secret`, `secrets/neo4j_password` montés via `secrets:` ; le `.env` (non sensible) est versionné |
| gobgp-neo4j-sync | **Docker secrets** (fichiers) + `*_FILE` | `secrets/ch_gobgp_reader_password`, `secrets/neo4j_password` montés via `secrets:` ; le `.env` (non sensible) est versionné |
| vector / `load_clickhouse.sh` | **Fichier secret partagé** | `gobgp/secrets/ch_gobgp_password` (`gobgp_writer`), monté dans vector, lu par le cron hôte |
| NetBox | **`env/*.env`** | `DB_PASSWORD`, `REDIS_PASSWORD`, etc. (fichiers d'environnement netbox-docker) |

!!! success "Secrets hors dépôt"
    Les dossiers `secrets/` sont exclus du versionnement (`.gitignore`). Les `.env`
    ClickHouse/Neo4j ne contiennent que des **chemins** `*_FILE`, jamais les mots de passe.

## Authentification par service

| Service | Authentification |
|---------|------------------|
| Neo4j | Utilisateur `neo4j` + mot de passe (obligatoire, lu depuis le secret) |
| ClickHouse | Utilisateurs XML chiffrés (`admin`, `lorion03vel`) ; utilisateur `default` **supprimé** ; utilisateurs SQL `gobgp_writer` (SELECT+INSERT) / `gobgp_reader` (SELECT) — **moindre privilège** par usage |
| receiver (webhooks) | **Signature HMAC-SHA512** vérifiée sur chaque webhook (`X-Hook-Signature`) |
| reconciler → NetBox | **Token API** NetBox (`Authorization: Token …`) |
| gobgpd (gRPC 50052) | *(aucune — API gRPC ouverte sur le port publié, lab uniquement)* |
| NetBox | Authentification applicative NetBox (session / token API) |

## Autorisation

- **Neo4j** : édition Community — un seul utilisateur `neo4j` (pas de RBAC multi-utilisateurs).
- **ClickHouse** : rôles SQL définis à l'init (`role_reader`, `role_writer`, `role_db_admin`)
  et utilisateurs applicatifs (`app_backend`, `bi_reader`, `db_migrator`) — voir
  [ClickHouse / Sécurité](../services/clickhouse/security.md).
- **NetBox** : permissions et tokens gérés dans NetBox.

## TLS / chiffrement en transit

!!! warning "Pas de TLS interne à ce jour"
    Les communications entre services se font en **HTTP/Bolt en clair**, sur des réseaux
    Docker **internes** non exposés à l'extérieur de l'hôte. Il n'y a **pas** de terminaison
    TLS ni de certificats gérés au niveau de la plateforme. La mise en place d'un reverse
    proxy avec TLS fait partie de la [Roadmap](roadmap.md).

## Reverse proxy

!!! note "Absent (exposition directe)"
    Aucun reverse proxy (Traefik/Nginx) n'est déployé. Les services exposent directement
    leurs ports sur l'hôte (Neo4j 7474/7687, ClickHouse 8123/9000, NetBox 9999). NetBox
    utilise en interne **nginx-unit** (serveur d'application inclus dans l'image), mais ce
    n'est pas un reverse proxy de plateforme.

## Isolation Docker

- Séparation par **réseaux bridge** : chaque VM a son réseau partagé
  (`lorionXXvel-network`) ; aucun conteneur n'est joignable depuis une autre VM
  autrement que par les ports publiés.
- **Aucun accès Internet** depuis les conteneurs (cf. [Infrastructure](infrastructure.md)) —
  réduit fortement la surface d'attaque sortante.
- Le **receiver n'est pas publié** sur l'hôte : joignable uniquement via le réseau Docker.

## Points d'attention connus

!!! danger "À corriger avant production"
    - Le `.env` de netbox-neo4j-sync a été **committé avec ses trois secrets**
      (token NetBox, secret webhook, mot de passe Neo4j) : ils restent dans
      l'**historique git**. Le secret webhook a déjà été **régénéré** (15/07/2026) ;
      restent à faire tourner : le **token NetBox** et le **mot de passe Neo4j**
      (`neo4j/secrets/neo4j_auth` était lui aussi versionné, dé-tracké depuis).
    - Les scripts d'init ClickHouse (`init/users-roles.sql`) créent des utilisateurs SQL
      avec **mots de passe en clair dans le SQL** (`app_backend`, `bi_reader`, `db_migrator`) :
      contenu d'exemple à revoir pour un usage réel.
    - Un mot de passe réel a été **committé en clair** dans
      `lorion01vel/gobgp/schemas/01_reader_role.sql` (utilisateur `gobgp_reader`) avant
      d'être remplacé par un placeholder : il reste dans l'**historique git** —
      **changer ce mot de passe** (`ALTER USER gobgp_reader IDENTIFIED BY …`) et mettre
      à jour le secret correspondant.
    - L'API **gRPC de gobgpd** est publiée sans authentification (`:50052`) : acceptable
      en lab isolé, à restreindre avant toute exposition.
    - Absence de TLS et de reverse proxy (voir ci-dessus).

Voir la sécurité détaillée de chaque service : [Neo4j](../services/neo4j/security.md) ·
[ClickHouse](../services/clickhouse/security.md) ·
[netbox-neo4j-sync](../services/netbox-neo4j-sync/security.md) ·
[NetBox](../services/netbox/security.md).

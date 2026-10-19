# ClickHouse — Configuration

Sources : `lorion03vel/clickhouse/compose.yml`, `.env`, `config/**`, `init/**`.

## Variables d'environnement (`clickhouse/.env`)

| Variable | Valeur réelle | Rôle |
|----------|---------------|------|
| `CLICKHOUSE_CONTAINER` | `lorion03vel-clickhouse` | Nom du conteneur |
| `TZ` | `Europe/Paris` | Fuseau horaire |
| `CLICKHOUSE_DB` | `lorion03vel` | Base créée à l'init par l'entrypoint |
| `CLICKHOUSE_USER` | `lorion03vel` | Utilisateur d'init (défini réellement en XML) |
| `CLICKHOUSE_PASSWORD_FILE` | `/run/secrets/clickhouse_password` | Secret lu par l'entrypoint |
| `CLICKHOUSE_SKIP_USER_SETUP` | `1` | Empêche l'entrypoint de créer l'utilisateur en clair |
| `CLICKHOUSE_ADMIN_USER` | `admin` | Compte de gestion (pour `manage-users.sh`) |
| `CLICKHOUSE_ADMIN_PASSWORD_FILE` | `secrets/clickhouse_admin_password` | Secret admin (**hôte**, pour le script) |

!!! info "Aucun mot de passe en clair dans `.env`"
    Le `.env` ne contient que des **chemins** `*_FILE`. Il est donc committable. Les mots de
    passe réels vivent dans `secrets/` (hors git) et dans les hachages SHA256 des XML.

## Fichiers de configuration

### `config/config.d/override.xml`

```xml
<clickhouse>
    <listen_host>0.0.0.0</listen_host>   <!-- rétabli (voir Architecture) -->
    <logger><level>information</level></logger>
    <display_name>lorion03vel</display_name>
</clickhouse>
```

### `config/users.d/admin.xml` et `lorion03vel.xml`

Utilisateurs **définis en XML**, mot de passe en **`password_sha256_hex`** (jamais en clair) :

```xml
<clickhouse>
  <users>
    <lorion03vel>
      <password_sha256_hex>…</password_sha256_hex>
      <networks><ip>::/0</ip><ip>0.0.0.0/0</ip></networks>
      <profile>default</profile><quota>default</quota>
      <access_management>1</access_management>
    </lorion03vel>
    <default remove="remove"></default>   <!-- l'accès anonyme est supprimé -->
  </users>
</clickhouse>
```

!!! tip "Régénérer un hash"
    ```bash
    printf 'MON_MDP' | sha256sum   # -> valeur à mettre dans password_sha256_hex
    ```
    Un utilisateur défini en XML est en **lecture seule via SQL** : `manage-users.sh` peut
    gérer d'**autres** utilisateurs (stockés en SQL dans le volume) mais pas modifier `admin`
    ou `lorion03vel` eux-mêmes.

## Scripts d'initialisation (`init/`)

Exécutés **au premier démarrage** (répertoire `/docker-entrypoint-initdb.d`) :

| Script | Contenu réel |
|--------|--------------|
| `schema.sql` | Base **`mydb`** + tables d'**exemple** : `events` (MergeTree, TTL 12 mois), `metrics`, `events_hourly_agg` (SummingMergeTree) + vue matérialisée `mv_events_hourly` |
| `users-roles.sql` | Rôles `role_reader` / `role_writer` / `role_db_admin` ; utilisateurs `app_backend`, `bi_reader`, `db_migrator` ; quota `quota_readonly` |

!!! warning "Écart à connaître : base d'init"
    L'entrypoint crée la base **`lorion03vel`** (`CLICKHOUSE_DB`), tandis que `schema.sql` crée
    et peuple **`mydb`** (schéma d'exemple). Le schéma métier réel reste donc à définir : ces
    tables sont un point de départ, pas le modèle final.

## Gestion des secrets

```yaml
secrets:
  clickhouse_password:
    file: ./secrets/clickhouse_password   # aligné au SHA256 de lorion03vel.xml
```

- `clickhouse_password` est monté sur `/run/secrets/clickhouse_password` (utilisé par
  l'entrypoint pour se connecter en tant que `lorion03vel` lors de l'init).
- `clickhouse_admin_password` **n'est pas** déclaré comme secret Docker : il n'est lu que
  **côté hôte** par `manage-users.sh` (le conteneur n'en a pas besoin).

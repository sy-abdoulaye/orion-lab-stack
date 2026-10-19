# ClickHouse — Dépannage

## « Connection reset by peer » sur 8123/9000

**Cause** : en montant `./config/config.d` sur `/etc/clickhouse-server/config.d`, le
`docker_related_config.xml` de l'image (qui ouvrait l'écoute réseau) est **masqué**. Sans
rétablissement, ClickHouse n'écoute que sur le loopback du conteneur.

**Solution** : `override.xml` déclare `<listen_host>0.0.0.0</listen_host>` (déjà présent dans le
dépôt). Vérifier qu'il est bien monté.

## L'utilisateur `default` fonctionne encore / accès anonyme

**Cause** : le retrait de `default` n'est pas pris en compte.

**Solution** : `lorion03vel.xml` contient `<default remove="remove"></default>`. Vérifier le
montage du fichier et redémarrer. Avec `CLICKHOUSE_SKIP_USER_SETUP=1`, l'entrypoint ne recrée
pas `default`.

## Les scripts d'init ne s'exécutent pas

**Cause** : `init/*.sql` ne s'exécute qu'au **premier démarrage** (volume vide).

**Solution** : pour rejouer, supprimer le volume `lorion03vel_clickhouse_data` (destructif) puis
redémarrer — voir [Maintenance](maintenance.md).

## Échec de connexion de l'entrypoint à l'init

**Cause** : le secret `clickhouse_password` ne correspond pas au `password_sha256_hex` de
`lorion03vel.xml`.

**Solution** : régénérer le hash et aligner le secret :
```bash
printf 'MON_MDP' | sha256sum          # -> à placer dans lorion03vel.xml
printf 'MON_MDP' > secrets/clickhouse_password
```

## `manage-users.sh` : « fichier secret introuvable »

**Cause** : `CLICKHOUSE_ADMIN_PASSWORD_FILE` pointe vers un fichier absent.

**Solution** : créer `secrets/clickhouse_admin_password` (aligné au hash de `admin.xml`), ou
exporter `CLICKHOUSE_ADMIN_PASSWORD` dans l'environnement.

## Le conteneur ne démarre pas après un montage de config

**Cause** : un fichier partiel a remplacé `config.xml`/`users.xml` racine.

**Solution** : ne monter que dans `config.d`/`users.d` (surcharges **fusionnées**), jamais
remplacer les fichiers racine — c'est le principe retenu dans le dépôt.

## Bonnes pratiques

!!! tip
    - Garder les mots de passe en **`password_sha256_hex`** (XML) et dans `secrets/` (hors git).
    - Remplacer le schéma d'exemple (`mydb`) par le modèle métier réel avant usage.
    - Sauvegarder avant toute suppression de volume.
    - Utiliser `/ping` pour les sondes (indépendant de l'authentification).

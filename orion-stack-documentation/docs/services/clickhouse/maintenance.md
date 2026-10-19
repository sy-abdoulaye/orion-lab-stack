# ClickHouse — Maintenance

## Gestion des utilisateurs : `manage-users.sh`

Script hôte (`clickhouse/manage-users.sh`) qui exécute les requêtes via `docker exec` + client
natif dans le conteneur (contourne l'interface HTTP et le proxy d'entreprise).

```bash
cd orion-lab-stack/lorion03vel/clickhouse
./manage-users.sh            # menu interactif (défaut)
./manage-users.sh list       # utilisateurs et rôles
./manage-users.sh databases  # bases de données
./manage-users.sh tables     # tables
./manage-users.sh create     # créer un utilisateur
./manage-users.sh delete     # supprimer un utilisateur
./manage-users.sh passwd     # modifier un mot de passe
./manage-users.sh roles      # gérer les rôles d'un utilisateur
./manage-users.sh create-role
```

Variables reconnues (lues depuis `.env` voisin, surchargées par l'environnement) :

| Variable | Défaut |
|----------|--------|
| `CLICKHOUSE_CONTAINER` | `lorion03vel-clickhouse` |
| `CLICKHOUSE_ADMIN_USER` | `admin` |
| `CLICKHOUSE_ADMIN_PASSWORD_FILE` | `secrets/clickhouse_admin_password` |

!!! tip
    Le mot de passe admin est lu **en priorité** depuis le fichier secret (`*_FILE`), résolu
    relativement au dossier du script s'il est en chemin relatif.

## Sauvegarde

=== "Copie du volume (arrêt recommandé)"

    ```bash
    docker compose stop clickhouse
    docker run --rm -v lorion03vel_clickhouse_data:/data -v "$PWD":/backup \
      registry.example.com/dockerhub/library/alpine \
      tar czf /backup/clickhouse_data_$(date +%F).tgz -C /data .
    docker compose start clickhouse
    ```

=== "Export logique d'une table"

    ```bash
    docker exec lorion03vel-clickhouse clickhouse-client -u lorion03vel --password 'lorion03vel' \
      -q "SELECT * FROM mydb.events FORMAT Native" > events.native
    ```

## Restauration

```bash
docker compose stop clickhouse
docker run --rm -v lorion03vel_clickhouse_data:/data -v "$PWD":/backup \
  registry.example.com/dockerhub/library/alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/clickhouse_data_<date>.tgz -C /data"
docker compose start clickhouse
```

## Rejouer l'initialisation

!!! danger "Destructif"
    Les scripts `init/*.sql` ne s'exécutent qu'avec un volume **vide**. Pour les rejouer :
    ```bash
    docker compose down
    docker volume rm lorion03vel_clickhouse_data   # PERTE DE DONNÉES
    docker compose up -d clickhouse
    ```

## Mise à jour

1. Adapter le tag d'image dans `clickhouse/compose.yml` (ex. `clickhouse-server:25.x-alpine`).
2. `docker compose pull clickhouse && docker compose up -d clickhouse`.
3. Vérifier `/ping` et `SELECT version();`.

## Commandes utiles

```bash
docker compose logs -f clickhouse
docker exec lorion03vel-clickhouse clickhouse-client -q "SELECT version()"
docker exec lorion03vel-clickhouse clickhouse-client -u lorion03vel --password 'lorion03vel' \
  -q "SELECT name, engine FROM system.tables WHERE database='mydb'"
```

# Runbook d'exploitation

Gestes courants et checklist. Toutes les commandes `docker compose` s'exécutent depuis
`orion-lab-stack/lorion03vel` (sauf mention NetBox).

## Contrôles quotidiens

```bash
docker compose ps                       # tous Up (healthy)
docker compose run --rm reconciler python -m admin stats
docker compose logs --since 1h reconciler | grep -E "Cycle terminé|Échec"
```

- [ ] Neo4j `healthy`
- [ ] receiver `healthy`
- [ ] reconciler : cycles réguliers sans `Échec`
- [ ] Compteurs `stats` cohérents avec NetBox

## Gestes fréquents

=== "Redémarrer un service"

    ```bash
    docker compose restart reconciler
    docker compose up -d --build receiver
    ```

=== "Forcer une resynchronisation"

    ```bash
    docker compose run --rm reconciler python -m admin init
    ```

=== "Réinitialiser le graphe"

    ```bash
    docker compose run --rm reconciler python -m admin wipe --yes
    docker compose run --rm reconciler python -m admin init
    ```

=== "Reconfigurer les webhooks"

    ```bash
    docker compose run --rm reconciler python -m admin setup-webhooks
    ```

## Rotation du secret de webhook

1. Générer : `python3 -c "import secrets; print(secrets.token_hex(32))"`.
2. Mettre à jour `WEBHOOK_SECRET` dans `netbox-neo4j-sync/.env`.
3. `docker compose up -d receiver`.
4. `docker compose run --rm reconciler python -m admin setup-webhooks` (propage à NetBox).

## Vérifier le flux temps réel

```bash
# Modifier un device dans NetBox (UI/API), puis :
docker compose logs --since 2m receiver | grep "Webhook appliqué"
docker logs --since 2m netbox-docker-netbox-worker-1 | grep -i webhook
```

## Incidents fréquents → où aller

| Symptôme | Piste |
|----------|-------|
| Neo4j `unhealthy` | [Neo4j / Dépannage](../services/neo4j/troubleshooting.md) |
| Webhook non appliqué | [NetBox / Dépannage](../services/netbox/troubleshooting.md) |
| Relations manquantes | [sync / Dépannage](../services/netbox-neo4j-sync/troubleshooting.md) |
| Connexion refusée conteneur↔service | [Réseau](../architecture/networking.md) |

## Checklist de mise en production

- [ ] `WEBHOOK_SECRET` fort (pas le placeholder)
- [ ] Token NetBox restreint (lecture DCIM/IPAM)
- [ ] Sauvegardes planifiées (PostgreSQL surtout)
- [ ] Secrets/`.env` sauvegardés hors dépôt
- [ ] Contraintes Neo4j présentes (`SHOW CONSTRAINTS`)
- [ ] Mots de passe d'exemple ClickHouse revus (si activé)

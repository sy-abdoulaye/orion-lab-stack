# Neo4j — Maintenance

## Sauvegarde

Les données vivent dans le volume nommé `neo4j_data`. Deux approches (édition Community) :

=== "Dump hors-ligne (recommandé)"

    ```bash
    # Arrêter le conteneur pour un dump cohérent
    docker compose stop neo4j
    docker run --rm \
      -v lorion03vel_neo4j_data:/data \
      -v "$PWD":/backup \
      registry.example.com/dockerhub/neo4j:5.26.0 \
      neo4j-admin database dump neo4j --to-path=/backup
    docker compose start neo4j
    ```

=== "Copie du volume"

    ```bash
    docker run --rm -v lorion03vel_neo4j_data:/data -v "$PWD":/backup \
      registry.example.com/dockerhub/library/alpine \
      tar czf /backup/neo4j_data_$(date +%F).tgz -C /data .
    ```

!!! note
    Le nom réel du volume est préfixé par le projet : `lorion03vel_neo4j_data`.
    Le vérifier avec `docker volume ls | grep neo4j`.

## Restauration

```bash
docker compose stop neo4j
docker run --rm -v lorion03vel_neo4j_data:/data -v "$PWD":/backup \
  registry.example.com/dockerhub/neo4j:5.26.0 \
  neo4j-admin database load neo4j --from-path=/backup --overwrite-destination=true
docker compose start neo4j
```

## Mise à jour

1. Modifier `IMAGE_NEO4J` dans `neo4j/.env` (ex. `neo4j:5.26.1`).
2. **Vérifier la compatibilité des plugins** (APOC et GDS doivent suivre la version mineure et
   rester en Java 17 pour la branche 5.26). Télécharger les JARs correspondants dans `plugins/`.
3. Recréer le conteneur :
   ```bash
   docker compose pull neo4j && docker compose up -d neo4j
   ```

!!! warning "Toujours aligner Neo4j ↔ APOC ↔ GDS"
    APOC suit la version de Neo4j (même `5.26.x`). GDS doit rester compatible Java 17
    (branche 2.13.x). Voir [Déploiement](deployment.md).

## Rollback

- Restaurer l'ancien tag dans `IMAGE_NEO4J`, remettre les anciens JARs dans `plugins/`, puis
  `docker compose up -d neo4j`.
- Si le graphe a été altéré, restaurer un **dump** (voir ci-dessus).

## Purge / réinitialisation du graphe

Via le CLI du sync (voir [netbox-neo4j-sync / CLI](../netbox-neo4j-sync/admin-cli.md)) :

```bash
docker compose run --rm reconciler python -m admin wipe --yes
docker compose run --rm reconciler python -m admin init   # reconstruit depuis NetBox
```

## Commandes utiles

```bash
docker compose logs -f neo4j
docker exec -ti lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>'
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' "SHOW CONSTRAINTS;"
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "MATCH (n) RETURN count(n);"
```

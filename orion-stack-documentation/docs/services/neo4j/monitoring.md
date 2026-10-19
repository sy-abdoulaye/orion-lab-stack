# Neo4j — Monitoring

## Healthcheck

Le healthcheck (défini dans `neo4j/compose.yml`) valide l'accès **authentifié** via
`cypher-shell`, en lisant le mot de passe depuis le secret monté (pas de mot de passe en clair
dans le Compose) :

```yaml
healthcheck:
  test:
    - CMD-SHELL
    - cypher-shell -u ${NEO4J_USER:-neo4j} -p "$$(cut -d/ -f2 /run/secrets/neo4j_auth)" 'RETURN 1' || exit 1
  interval: 30s
  timeout: 10s
  retries: 5
```

!!! info "Pourquoi pas `curl`"
    L'image `neo4j:5.26.0` ne contient **pas** `curl` ; un healthcheck `curl http://localhost:7474/`
    rendait le conteneur `unhealthy` bien que fonctionnel. `cypher-shell` (présent dans l'image)
    teste en plus l'**authentification** et le moteur.

Vérifier l'état :

```bash
docker inspect --format '{{.State.Health.Status}}' lorion03vel-neo4j   # -> healthy
docker compose ps neo4j
```

## Logs

```bash
docker compose logs -f neo4j
docker compose logs neo4j | grep -i "apoc\|gds\|Started\|WARN\|ERROR"
```

Le volume `neo4j_logs` (`/logs`) conserve les journaux (`neo4j.log`, `debug.log`).

## Métriques & indicateurs

Requêtes Cypher utiles pour surveiller le graphe :

```cypher
// Volumétrie
MATCH (n) RETURN count(n) AS noeuds;
MATCH ()-[r]->() RETURN count(r) AS relations;

// Répartition par label (rôle)
MATCH (n) RETURN labels(n)[0] AS role, count(*) AS n ORDER BY n DESC;

// Contraintes en place
SHOW CONSTRAINTS;
```

!!! tip "Suivi côté sync"
    Le CLI d'administration fournit un aperçu rapide :
    ```bash
    docker compose run --rm reconciler python -m admin stats
    # Nœuds : 109 | EST_CONNECTE_A : 297 | Rôles/labels (34) : ...
    ```

## Performances

- Le **page cache** (6 Go) doit idéalement contenir les données chaudes ; surveiller la RAM de
  l'hôte.
- Les **contraintes d'unicité** (`Id` par label de rôle) créent des index qui accélèrent les
  `MERGE`/`MATCH` par `Id`.
- Le `debug.log` remonte les requêtes lentes et les avertissements du planificateur.

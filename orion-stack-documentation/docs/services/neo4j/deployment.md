# Neo4j — Déploiement

## Prérequis

- Réseau `lorion03vel-network` existant.
- Secret `neo4j/secrets/neo4j_auth` présent (format `neo4j/<motdepasse>`).
- Plugins présents dans `neo4j/plugins/` (voir ci-dessous).

## Installation des plugins (hors-ligne)

Le conteneur n'ayant pas d'accès Internet, les JARs sont téléchargés **sur l'hôte** (via proxy)
puis déposés dans `neo4j/plugins/`. Extrait réel de `cmd.md` :

```bash
cd orion-lab-stack/lorion03vel/neo4j
mkdir -p plugins
curl -sL -o plugins/apoc-5.26.27-core.jar \
  "https://github.com/neo4j/apoc/releases/download/5.26.27/apoc-5.26.27-core.jar"
curl -sL -o plugins/neo4j-graph-data-science-2.13.2.jar \
  "https://github.com/neo4j/graph-data-science/releases/download/2.13.2/neo4j-graph-data-science-2.13.2.jar"
```

!!! danger "Compatibilité Java — contrainte critique"
    Neo4j 5.26 tourne sous **Java 17**. GDS doit donc être compilé pour Java 17 :

    | GDS | Bytecode | Compatible Neo4j 5.26 |
    |-----|----------|-----------------------|
    | **2.13.2** | Java 17 | ✅ (version retenue) |
    | ≥ 2.27 / 2026.x | Java 21 | ❌ `UnsupportedClassVersionError` |

    Rester sur **GDS 2.13.x** et **APOC 5.26.x** tant que Neo4j est en 5.26.

## Déploiement

=== "Via le projet lorion03vel"

    ```bash
    cd orion-lab-stack/lorion03vel
    docker compose up -d neo4j
    ```

=== "Attendre que Neo4j soit prêt"

    ```bash
    until docker exec lorion03vel-neo4j cypher-shell \
      -u neo4j -p "$(cut -d/ -f2 neo4j/secrets/neo4j_auth)" "RETURN 1" >/dev/null 2>&1; do
      sleep 3
    done
    echo "Neo4j prêt"
    ```

## Vérification du bon fonctionnement

```bash
# Versions des plugins
docker exec lorion03vel-neo4j cypher-shell -u neo4j -p '<mdp>' \
  "RETURN apoc.version() AS apoc, gds.version() AS gds;"
# -> "5.26.27", "2.13.2"

# Accès Browser
# http://<hôte>:7474  (login neo4j)
```

!!! success "Résultat attendu"
    - Conteneur `Up (healthy)`.
    - `apoc.version()` = `5.26.27`, `gds.version()` = `2.13.2`.
    - Aucun `UnsupportedClassVersionError` dans les logs.

## Réseau préexistant

Si le réseau existe déjà (partagé), il doit être `external`. En cas d'erreur
`network ... was found but has incorrect label`, voir [Dépannage](troubleshooting.md).

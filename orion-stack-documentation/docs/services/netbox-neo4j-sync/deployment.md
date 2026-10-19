# netbox-neo4j-sync — Déploiement

## Images (build local via proxy)

Les deux services sont **construits localement** depuis
`registry.example.com/dockerhub/library/python:3.12-slim`. Le `pip install` nécessitant PyPI,
le **proxy est passé en build-arg** (le conteneur n'a pas d'accès Internet direct) :

```yaml
build:
  context: .
  dockerfile: Dockerfile.receiver
  args:
    http_proxy: ${BUILD_HTTP_PROXY:-}
    https_proxy: ${BUILD_HTTPS_PROXY:-}
```

`Dockerfile.reconciler` copie en plus le module `admin/` (pour le CLI).

## Réseaux

Les deux services sont attachés au réseau partagé de la VM, **`lorion03vel-network`**,
où vivent aussi NetBox et Neo4j (joignabilité dans les deux sens) :

```yaml
networks:
  lorion03vel-network: { name: lorion03vel-network, external: true }
```

## Prérequis

1. NetBox en fonctionnement (projet `netbox-docker`).
2. Neo4j en fonctionnement.
3. `.env` renseigné (token, secret, mot de passe Neo4j).
4. `BUILD_HTTP_PROXY` / `BUILD_HTTPS_PROXY` définis pour le build.

## Déploiement

=== "Via le projet lorion03vel"

    ```bash
    cd orion-lab-stack/lorion03vel
    docker compose build receiver reconciler
    docker compose up -d receiver reconciler
    docker compose ps
    ```

=== "Configurer NetBox puis vérifier"

    ```bash
    docker compose run --rm reconciler python -m admin setup-webhooks
    docker compose run --rm reconciler python -m admin init
    docker compose run --rm reconciler python -m admin stats
    ```

## Vérification du bon fonctionnement

```bash
# receiver sain (Neo4j joignable)
docker compose ps receiver          # -> Up (healthy)

# reconciler : premier cycle
docker compose logs reconciler | grep "Cycle terminé"
# -> Cycle terminé : 109 device(s), 283 relation(s) EST_CONNECTE_A.
```

Test temps réel : modifier un device dans NetBox → le receiver logge
`Webhook appliqué: event=updated model=device id=…` (200).

!!! success "Résultat attendu"
    - `receiver` : `Up (healthy)`.
    - `reconciler` : cycles réguliers, compteurs cohérents avec NetBox.
    - Webhooks NetBox → receiver en `200`, signatures valides.

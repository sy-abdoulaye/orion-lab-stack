# Neo4j — Dépannage

Problèmes réellement rencontrés lors de la mise en place, avec leur résolution.

## `invalid reference format: repository name must be lowercase`

**Cause** : `$` manquant dans la substitution de l'image (`{IMAGE_NEO4J...}` au lieu de
`${IMAGE_NEO4J...}`) → la variable n'est pas interpolée et contient des majuscules.

**Solution** : `image: registry.example.com/dockerhub/${IMAGE_NEO4J:-neo4j:5.26.0}`.

## `The secret file '/run/secrets/neo4j_auth' does not exist or is not readable`

**Cause** : secret absent, ou droits insuffisants (le user `neo4j` uid 7474 ne peut pas lire le
fichier), ou secret déclaré sous un autre nom.

**Solution** : vérifier que `neo4j/secrets/neo4j_auth` existe, est lisible, et que le service
référence bien ce secret. Format attendu : `neo4j/<motdepasse>`.

## `UnsupportedClassVersionError ... class file version 65.0`

**Cause** : un plugin (typiquement GDS) est compilé pour **Java 21** alors que Neo4j 5.26 tourne
sous **Java 17** (max class version 61).

**Solution** : utiliser **GDS 2.13.2** (Java 17). Voir [Déploiement](deployment.md).

```bash
# Vérifier le bytecode d'un Jar GDS
unzip -p plugins/<gds>.jar $(unzip -l plugins/<gds>.jar | grep -m1 '\.class$' | awk '{print $4}') \
  | od -An -tu1 -j7 -N1   # 61 = Java 17 (OK), 65 = Java 21 (KO)
```

## Enterprise : `you must accept the license agreement`

**Cause** : usage d'une image `-enterprise` sans licence.

**Solution** : utiliser l'édition **Community** (`neo4j:5.26.0`). L'Enterprise nécessiterait
`NEO4J_ACCEPT_LICENSE_AGREEMENT=yes`.

## `network lorion03vel-network was found but has incorrect label`

**Cause** : le réseau existait déjà (créé hors Compose) et n'était pas déclaré `external`.

**Solution** : déclarer le réseau `external: true` dans les fichiers compose, ou recréer le
réseau. Le réseau est **partagé** volontairement entre les services.

## Conteneur `unhealthy` alors que Neo4j fonctionne

**Cause** : ancien healthcheck basé sur `curl` (absent de l'image).

**Solution** : healthcheck `cypher-shell` (voir [Monitoring](monitoring.md)).

## Bonnes pratiques

!!! tip
    - Toujours **aligner** Neo4j ↔ APOC ↔ GDS (versions + Java).
    - Sauvegarder avant toute mise à jour majeure.
    - Ne pas publier 7474/7687 au-delà du réseau de confiance (pas de TLS).
    - Utiliser le CLI `admin wipe/init` plutôt que des suppressions manuelles pour
      réinitialiser le graphe de façon cohérente.

# FAQ

??? question "Pourquoi Neo4j **et** ClickHouse ?"
    Ils répondent à des besoins différents : **Neo4j** pour le **parcours de graphe** (topologie,
    voisinage, GDS), **ClickHouse** pour l'**analytique OLAP** (agrégations, séries temporelles).
    ClickHouse reçoit les données **BGP-LS** collectées sur `lorion01vel` (gobgp + vector) ;
    `gobgp-neo4j-sync` les projette ensuite dans le graphe Neo4j.

??? question "Pourquoi pas de Kafka / bus de messages ?"
    La synchronisation temps réel repose sur les **webhooks NetBox** directs vers le receiver,
    sans infrastructure supplémentaire. Un bus d'événements est envisagé dans la
    [Roadmap](../architecture/roadmap.md).

??? question "Pourquoi `http://netbox:8080` et pas `localhost:9998` dans le `.env` ?"
    Les services de sync tournent **en conteneur**, sur le réseau `lorion03vel-network`, où
    NetBox est joignable par son nom interne `netbox:8080`. `localhost:9998` (port publié) ne
    vaut que **depuis l'hôte**. Voir [Réseau](../architecture/networking.md).

??? question "Pourquoi le webhook renvoyait 400 « Payload incomplet » ?"
    NetBox 4.5 envoie `object_type` (`dcim.device`) et non `model`. Le receiver a été adapté pour
    en extraire le nom du modèle. Voir [sync / Receiver](../services/netbox-neo4j-sync/receiver.md).

??? question "Pourquoi GDS 2.13.2 et pas la dernière version ?"
    Neo4j 5.26 tourne sous **Java 17**. GDS ≥ 2.27 est compilé pour **Java 21** →
    `UnsupportedClassVersionError`. On reste sur la branche **2.13.x** (Java 17).

??? question "Comment reconstruire entièrement le graphe ?"
    ```bash
    docker compose run --rm reconciler python -m admin wipe --yes
    docker compose run --rm reconciler python -m admin init
    ```
    Le graphe est **entièrement dérivable** de NetBox (source de vérité).

??? question "Le label d'un device, c'est quoi exactement ?"
    Le **rôle feuille** du device (ex. `:spinebib`). La propriété `Fonction` porte le **rôle
    racine** (ex. `coreip`). Voir [Modèle de données](../services/netbox-neo4j-sync/data-model.md).

??? question "Pourquoi le receiver n'est-il pas exposé sur l'hôte ?"
    Il est appelé par NetBox **en interne** (réseau `lorion03vel-network`). Ne pas le publier
    réduit la surface d'exposition.

??? question "Comment installer les plugins Neo4j sans Internet ?"
    Les JARs sont téléchargés **sur l'hôte** (via proxy) puis déposés dans `neo4j/plugins/`
    (monté dans `/plugins`). Voir [Neo4j / Déploiement](../services/neo4j/deployment.md).

??? question "Où sont les mots de passe ?"
    Dans des **fichiers secrets** (`secrets/`, hors git) ou des `.env` non versionnés, et sous
    forme de **hachages SHA256** dans les XML ClickHouse. Jamais en clair dans les fichiers
    versionnés. Voir [Sécurité globale](../architecture/security.md).

??? question "Comment activer ClickHouse ?"
    Décommenter son entrée dans l'`include` du `docker-compose.yml`, créer les secrets, puis
    `docker compose up -d clickhouse`. Voir [ClickHouse / Déploiement](../services/clickhouse/deployment.md).

??? question "Que faire si un webhook n'arrive pas ?"
    Diagnostiquer **du producteur vers le consommateur** : vérifier le **worker NetBox** (qui
    émet), l'**Event Rule**, puis le **receiver**. Voir [NetBox / Worker](../services/netbox/worker.md).

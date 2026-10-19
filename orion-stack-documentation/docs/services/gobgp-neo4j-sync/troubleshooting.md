# gobgp-neo4j-sync — Dépannage

## Lire les compteurs de cycle

La ligne de bilan de chaque cycle est le premier outil de diagnostic :

```text
Cycle topologie terminé : 21/31 routeur(s) rattachés à un équipement, 563 préfixe(s),
611/676 annonce(s) IGP, 74/102 lien(s) ; 10 routeur(s), 65 annonce(s), 28 lien(s)
sans équipement correspondant.
```

Un ratio `rattachés/total` bas signifie que des routeurs BGP-LS n'ont **pas
d'équipement NetBox homonyme** — c'est un problème de données (nommage), pas un bug.

## Symptômes courants

??? failure "`Connection refused` / timeout vers ClickHouse"
    - `CLICKHOUSE_HOST` doit être **`lorion03vel-clickhouse`** (nom Docker). L'IP hôte
      `10.10.3.141` échoue depuis un conteneur de la même VM (hairpin NAT bloqué).
    - Vérifier que ClickHouse est healthy : `docker ps --filter name=clickhouse`.

??? failure "`Authentication failed` ClickHouse"
    Mot de passe `gobgp_reader` désynchronisé. Retester à la main :
    ```bash
    docker exec -it lorion03vel-clickhouse clickhouse-client \
      -u gobgp_reader --password '<mdp>' -q "SELECT count() FROM gobgp.bgp_ls_nodes"
    ```
    Si l'utilisateur n'existe pas : rejouer `lorion01vel/gobgp/schemas/01_reader_role.sql`.

??? failure "`Failed to read from defunct connection` (Neo4j)"
    Apparaît quand Neo4j **redémarre** (maintenance, redéploiement) : le driver se
    reconnecte au cycle suivant. Bénin si les cycles reprennent ensuite ; sinon vérifier
    `NEO4J_PASSWORD` et l'état du conteneur Neo4j.

??? failure "Beaucoup d'éléments « sans équipement correspondant »"
    - `netbox-neo4j-sync` a-t-il créé les équipements ? (`python -m admin stats` côté
      sync NetBox).
    - Le nom NetBox et le `NodeName` BGP-LS doivent correspondre (match insensible à la
      casse, espaces retirés). Comparer :
      ```sql
      SELECT DISTINCT NodeName FROM gobgp.SAFI_LINK_STATE_NODE FINAL LIMIT 20
      ```
      avec les `Nom` des nœuds Neo4j.

??? failure "Cycle monitor toujours à 0 mise à jour"
    Normal si le réseau est stable (aucun événement dans la fenêtre). Pour vérifier que
    la chaîne amont fonctionne :
    ```sql
    SELECT max(Age) FROM gobgp.monitor_bgp_ls_link
    ```
    Si `max(Age)` est vieux, le problème est en amont (vector ou gobgp — voir leurs
    pages de dépannage).

??? failure "Le graphe contient des données BGP périmées"
    Le cycle topologie purge à chaque passage. Pour repartir de zéro :
    ```bash
    docker compose run --rm reconciler-gobgp-neo4j python -m admin wipe --yes
    docker compose run --rm reconciler-gobgp-neo4j python -m admin init
    ```

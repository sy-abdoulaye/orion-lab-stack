# gobgp — Dépannage

Le helper **`gobgp.sh`** (racine du dossier) enveloppe les commandes usuelles :

| Commande | Effet |
|----------|-------|
| `sh gobgp.sh status` | État des conteneurs |
| `sh gobgp.sh neighbors` | Sessions BGP (état, préfixes reçus) |
| `sh gobgp.sh adj-in <IP>` / `adj-out <IP>` | Routes reçues / annoncées pour un peer |
| `sh gobgp.sh rib` / `rib-summary` | Table de routage globale |
| `sh gobgp.sh pull-ls` / `pull-bgp` | Déclencher une collecte manuellement |
| `sh gobgp.sh load-ch` | Déclencher le chargement ClickHouse manuellement |
| `sh gobgp.sh logs` / `logs-cron` | Logs daemon / logs des scripts cron |
| `sh gobgp.sh shell` | Shell dans le conteneur client |
| `sh gobgp.sh reset <IP>` / `softreset <IP>` | Reset (soft) d'une session BGP |

## Symptômes courants

??? failure "Sessions BGP en `Active`/`Idle` (jamais `Establ`)"
    - Vérifier la joignabilité des réflecteurs depuis l'hôte, et que le port **1790**
      est bien publié (`docker port gobgp-daemon`).
    - Les peers de la conf prod doivent accepter la session depuis l'IP de la VM —
      côté réflecteur, le peer pointe vers `203.0.113.1` (port distant 1790 si la
      session est initiée par le réflecteur).
    - `sh gobgp.sh logs` : rejets/refus visibles côté daemon.

??? failure "`gobgp-client` redémarre en boucle"
    Le client exige le daemon **healthy**. Si le healthcheck échoue :
    `docker inspect gobgp-daemon --format '{{json .State.Health}}'` — le test exécute
    `gobgp global` en local dans le conteneur.

??? failure "CSV `PROD__*` absents ou vieux"
    - `sh gobgp.sh crontab` : le crontab doit contenir les entrées h+0 / h+5.
    - `sh gobgp.sh logs-cron` : erreurs des scripts.
    - Déclencher à la main : `sh gobgp.sh pull-ls` puis vérifier `data/`.

??? failure "`MONITOR__*.csv` ne grossissent plus"
    Le process `prod_MONITOR_DECODE_BGP` (lancé par l'entrypoint du client) est peut-être
    mort : `docker exec gobgp-client ps aux | grep MONITOR`, puis
    `docker compose restart gobgp-cli`. Vérifier aussi `/var/log/gobgp/monitor.log`
    dans le conteneur.

??? failure "`load_clickhouse.sh` en `[FAIL]`"
    - Secret manquant : `secrets/ch_gobgp_password` (message explicite au lancement).
    - ClickHouse injoignable : tester `clickhouse-client --host 10.10.3.141 --port 9000`
      depuis l'hôte. **Ne pas** utiliser le nom `lorion03vel` (périmé dans `/etc/hosts`).
    - Erreur de schéma : comparer l'en-tête du CSV aux colonnes de la table
      (`schemas/00_setup.sql`).

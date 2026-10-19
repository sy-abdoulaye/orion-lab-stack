# gobgp — Déploiement

## Prérequis

- Les **binaires de production** dans `bin/` (`gobgpd`, `gobgp`) et les **scripts de
  collecte** dans `bin/bgpls/` (`prod__pull_bgp_ls`, `prod__pull_safi_LINK_STATE`,
  `prod_MONITOR_DECODE_BGP`) — copiés depuis la VM prod, ils ne sont pas dans git.
- `gobgpd_all.conf` dans `daemon/` (copie de la config prod).
- Le `.env` du dossier (variables de **proxy de build** uniquement).
- Les ports **1790** et **50052** libres sur l'hôte (179/50051 = gobgpd prod systemd).

## Démarrage

=== "Depuis le poste d'admin"

    ```bash
    make deploy VM=lorion01vel     # rsync + make up sur la VM
    ```

=== "Sur la VM"

    ```bash
    cd /data/orion-lab-stack/lorion01vel
    make up          # réseau lorion01vel-network (si absent) + build + up -d
    make ps
    ```

Le client attend que le daemon soit **healthy** avant de démarrer (dépendance
`service_healthy` du compose).

## Chargement ClickHouse (cron hôte)

Le chargement des snapshots n'est **pas** dans un conteneur — l'installer une fois dans
le crontab de l'hôte :

```text
7 * * * * cd /data/orion-lab-stack/lorion01vel/gobgp && ./scripts/load_clickhouse.sh >> scripts/load_clickhouse.log 2>&1
```

et créer le secret `secrets/ch_gobgp_password` (mot de passe de `gobgp_writer`,
`chmod 600`).

## Vérifications

```bash
sh gobgp.sh status          # état des conteneurs
sh gobgp.sh neighbors       # sessions BGP (Establ attendu)
sh gobgp.sh logs            # logs gobgpd
ls -lh data/                # CSV PROD__ / MONITOR__ produits
tail scripts/load_clickhouse.log   # [OK] fichier → table (n lignes)
```

!!! success "Stack opérationnelle"
    - `gobgp-daemon` **healthy**, sessions `Establ` vers les réflecteurs.
    - CSV `PROD__*` re-générés toutes les heures, `MONITOR__*` qui grossissent.
    - `load_clickhouse.log` en `[OK]` à h+7 ; tables `gobgp.*` alimentées.

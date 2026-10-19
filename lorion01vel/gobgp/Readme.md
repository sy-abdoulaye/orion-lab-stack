# Stack GoBGP BGP-LS – Docker Compose

## Structure du projet
<!--  -->
```
gobgp-stack/
├── docker-compose.yml          ← Orchestration
├── gobgpd_all.conf             ← Config BGP-LS (copier depuis la VM)
├── gobgp.sh                    ← Script helper CLI
│
├── opt-gobgp/                  ← Miroir de /opt/gobgp sur la VM
│   ├── gobgpd                  ← Binaire daemon   (obligatoire)
│   ├── gobgp                   ← Binaire CLI       (optionnel)
│   └── bin/
│       ├── prod__pull_safi_LINK_STATE   (obligatoire)
│       └── prod__pull_bgp_ls            (obligatoire)
|       |__ prod_MONITOR_DECODE_BGP       (obligatoire)
│
├── gobgpd/
│   ├── Dockerfile
│   └── entrypoint.sh           ← Démarre cron + gobgpd
└── gobgp-cli/
└── Dockerfile
```

---

## Étape 1 — Copier les fichiers depuis la VM prod

```bash
SRC="user@prod-router"

# Binaires
scp $SRC:/opt/gobgp/gobgpd          opt-gobgp/gobgpd
scp $SRC:/opt/gobgp/gobgp           opt-gobgp/gobgp       # si présent

# Configuration
scp $SRC:/opt/gobgp/gobgpd_all.conf gobgpd_all.conf

# Scripts de collecte
scp $SRC:/opt/gobgp/bin/prod__pull_safi_LINK_STATE  opt-gobgp/bin/
scp $SRC:/home/tmac/go/build/prod__pull_bgp_ls      opt-gobgp/bin/
```

---

## Étape 2 — Démarrer la stack

```bash
chmod +x gobgp.sh
sh gobgp.sh up
```

Le container lance automatiquement :
- `gobgpd` avec `gobgpd_all.conf`
- `crond` avec les mêmes plannings que la VM prod :
- `0 * * * *`  → `prod__pull_safi_LINK_STATE`
- `10 * * * *` → `prod__pull_bgp_ls`

---

## Étape 3 — Vérifier

```bash
sh gobgp.sh status        # containers actifs
sh gobgp.sh logs          # logs gobgpd
sh gobgp.sh logs-cron     # logs des scripts cron
sh gobgp.sh neighbors     # état des sessions BGP
```

---

## Utilisation courante

```bash
sh gobgp.sh neighbors                 # état de tous les peers
sh gobgp.sh adj-in  <IP_PEER>         # routes reçues
sh gobgp.sh adj-out <IP_PEER>         # routes annoncées
sh gobgp.sh rib                       # table de routage globale
sh gobgp.sh pull-ls                   # déclencher la collecte LINK_STATE manuellement
sh gobgp.sh pull-bgp                  # déclencher prod__pull_bgp_ls manuellement
sh gobgp.sh crontab                   # vérifier le crontab dans le container
sh gobgp.sh shell                     # shell interactif dans le container
```

---

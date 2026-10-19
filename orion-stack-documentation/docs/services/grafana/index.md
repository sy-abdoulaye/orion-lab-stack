# Grafana

Visualisation des données de la plateforme — **première stack de la VM
lorion02vel**, hébergée dans `lorion02vel/grafana/` du dépôt.

| Élément | Valeur |
|---------|--------|
| Image | `orion/grafana-clickhouse` (build local : Grafana 12.1.1 + plugin ClickHouse) |
| Conteneur | `lorion02vel-grafana` |
| Réseau | `lorion02vel-network` (réseau partagé de la VM) |
| Accès | `http://10.10.2.11:3000/` |
| Datasource | ClickHouse lorion03vel — `10.10.3.141:9000` (natif, inter-VM) |

## Pattern

La stack suit les conventions communes du dépôt :

- **Miroir interne** : l'image de base vient de `registry.example.com/dockerhub` ;
  le plugin `grafana-clickhouse-datasource` est installé **au build** via le
  proxy d'entreprise (`BUILD_HTTP_PROXY`) — aucun accès Internet à l'exécution.
- **Secrets en fichiers** (`grafana/secrets/`, hors git) montés via `secrets:` :
  mot de passe admin et clé de signature via la convention Grafana `GF_*__FILE`,
  mot de passe ClickHouse exporté par un entrypoint enveloppant pour
  l'interpolation du provisioning.
- **Réseau partagé** `lorion02vel-network` (`external: true`), créé par `make up`.

## Gestion des utilisateurs

- Auto-inscription **désactivée**, anonyme **désactivé**, création d'org
  **désactivée** ; tout nouveau compte naît **Viewer** (lecture seule).
- Cycle de vie des comptes : `lorion02vel/grafana/manage-users.sh`
  (`list`, `create`, `set-role`, `reset-password`, `delete`) — API locale
  authentifiée par le secret admin, même esprit que le `manage-users.sh`
  de ClickHouse.

## Sécurité

- Datasource ClickHouse en **lecture seule** : utilisateur dédié `grafana`
  (rôle `role_grafana_reader`, `SELECT` sur `gobgp.*` uniquement), déclaré
  côté lorion03vel — Grafana ne peut ni écrire ni lire d'autres bases.
- Datasource **non éditable dans l'UI** (`editable: false`) et dashboards
  versionnés dans le dépôt (provider en lecture seule) : la configuration
  est entièrement déclarative.
- Analytics, check d'updates, news et snapshots externes désactivés.

## Déploiement

```bash
make deploy VM=lorion02vel SECRETS=1   # premier déploiement (pousse les secrets)
make deploy VM=lorion02vel             # suivants (les secrets de la VM font foi)
```

Détails (bootstrap des secrets, permissions, dépannage) :
`lorion02vel/grafana/README.md` dans le dépôt.

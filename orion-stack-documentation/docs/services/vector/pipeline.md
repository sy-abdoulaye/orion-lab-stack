# vector — Pipeline

Le pipeline (`vector.yaml`) suit le schéma **source → route → remap → sinks**, avec un
pipeline par type de fichier.

## Source : `file`

```yaml
sources:
  monitor_files:
    type: file
    include: [/data/gobgp/MONITOR__*.csv]
    fingerprint:
      strategy: checksum
      lines: 2
```

!!! warning "Deux subtilités éprouvées en test"
    - **`lines: 2`** : `MONITOR__bgp_ls_prefixeV4.csv` et `…V6.csv` ont un **header
      strictement identique** — un checksum sur 1 ligne (défaut) les confond. On hashe
      header + première ligne de données pour les distinguer.
    - La stratégie **`device_and_inode` a été testée et écartée** : elle perd/corrompt
      des données après troncature du fichier (bug constaté en test).

## Route : un flux par fichier

Le transform `route_monitor` aiguille chaque ligne selon `.file` et **élimine la ligne
d'en-tête** (comparaison du message à l'en-tête connu du fichier). `reroute_unmatched:
false` : toute ligne d'un fichier inattendu est abandonnée.

## Remap : parsing CSV défensif (VRL)

Chaque route a son transform `parse_*` qui découpe la ligne (`split!(.message, ";")`) et
construit l'objet typé attendu par la table cible :

```text
"Best": fields[3] == "true",          # bool sans to_bool! (jamais d'exception)
"Asn":  to_int(fields[6]) ?? 0,       # int avec repli 0 si champ vide
```

!!! note "Pourquoi `== \"true\"` et `?? 0` plutôt que `to_bool!`/`to_int!`"
    Certains attributs BGP optionnels (ex. `AtomicAggregate`) arrivent **vides**. Les
    variantes `!` lèveraient une erreur et feraient perdre l'événement ; les comparaisons
    et coalescences n'échouent jamais.

## Sinks : ClickHouse HTTP

Sept sinks identiques (un par table), insertion `json_each_row` :

| Fichier source | Table ClickHouse |
|----------------|------------------|
| `MONITOR__bgp_ipv4Unicast.csv` | `gobgp.monitor_bgp_ipv4unicast` |
| `MONITOR__bgp_ls_link.csv` | `gobgp.monitor_bgp_ls_link` |
| `MONITOR__bgp_ls_node.csv` | `gobgp.monitor_bgp_ls_node` |
| `MONITOR__bgp_ls_prefixeV4.csv` | `gobgp.monitor_bgp_ls_prefixev4` |
| `MONITOR__bgp_ls_prefixeV6.csv` | `gobgp.monitor_bgp_ls_prefixev6` |
| `MONITOR__bgp_lu.csv` | `gobgp.monitor_bgp_lu` |
| `MONITOR__bgp_vpn.csv` | `gobgp.monitor_bgp_vpn` |

```yaml
endpoint: http://10.10.3.141:8123
auth: {strategy: basic, user: gobgp_writer, password: "${CLICKHOUSE_PASSWORD}"}
proxy: {no_proxy: ["10.10.3.141"]}
```

- **`no_proxy`** : le proxy d'entreprise ne doit pas intercepter le trafic vers
  ClickHouse (même précaution que `load_clickhouse.sh`, qui lui passe au natif).
- **`${CLICKHOUSE_PASSWORD}`** est injecté par l'entrypoint custom depuis le secret
  monté `/run/secrets/ch_gobgp_password` — même credential que le chargement cron
  (rôle `role_gobgp_writer`). Le conteneur **refuse de démarrer** si le secret manque.

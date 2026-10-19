"""Reconciler gobgp (ClickHouse) -> Neo4j : deux boucles indépendantes.

Le graphe Neo4j est partagé avec netbox-neo4j-sync : les nœuds équipement
existent déjà (propriété `Nom`). Aucun nœud Router n'est créé : chaque routeur
BGP-LS est résolu vers un équipement par son nom (match insensible à la casse),
via les tables nœuds ClickHouse (IgpRouterId/RouterId -> NodeName). Les
routeurs sans nom ou sans équipement correspondant sont ignorés (comptés dans
les logs) ainsi que leurs liens/annonces.

1) Topologie (RECONCILE_INTERVAL_SECONDS) : pull complet des tables d'état
   (bgp_ls_*, SAFI_LINK_STATE_*), upsert props équipement/Prefix/ISIS/
   ANNOUNCES_PREFIX avec l'état courant consolidé, puis purge de ce qui a disparu.
2) Monitor (MONITOR_POLL_INTERVAL_SECONDS) : lit les tables d'événements
   monitor_bgp_ls_*/monitor_bgp_* sur une fenêtre glissante et met à jour
   uniquement Withdraw/LastEventAge sur les relations déjà existantes, sans
   jamais réécrire les propriétés posées par le cycle topologie. Les tables
   monitor_bgp_ipv4unicast/lu/vpn créent en plus des relations ANNOUNCES_ROUTE.

Aucune donnée n'est retenue entre deux cycles (pas de watermark persisté) : la
fenêtre glissante du cycle monitor chevauche volontairement le cycle précédent,
les mises à jour étant idempotentes.
"""

from __future__ import annotations

import signal
import threading
import time

from common import mapping
from common.clickhouse_client import ClickHouseReader
from common.config import settings
from common.logging import get_logger
from common.neo4j_client import Neo4jClient

log = get_logger("reconciler")

_running = threading.Event()
_running.set()


def _handle_stop(signum, _frame) -> None:
    """Gestion des signaux SIGTERM et SIGINT pour un arrêt propre du reconciler."""
    log.info("Signal %s reçu : arrêt après le cycle en cours.", signum)
    _running.clear()


# ── Résolution identifiants BGP-LS -> nom d'équipement NetBox ──────────────

def _resolution_maps(ch: ClickHouseReader) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Construit IgpRouterId -> nom, RouterId -> nom (noms en minuscules) et
    RouterId -> IgpRouterId depuis les tables d'état. Reconstruit à chaque
    cycle : les nœuds équipement NetBox sont réécrits par netbox-neo4j-sync,
    on ne peut pas y stocker durablement les identifiants BGP-LS."""
    name_by_igp: dict[str, str] = {}
    name_by_router_id: dict[str, str] = {}
    igp_by_router_id: dict[str, str] = {}
    for row in ch.query_dicts("SELECT DISTINCT Node, IgpRouter FROM bgp_ls_nodes FINAL WHERE Node != ''"):
        name_by_igp[row["IgpRouter"]] = row["Node"].strip().lower()
    for row in ch.query_dicts(
        "SELECT DISTINCT NodeName, NodeLocalIgpRouterId, NodeRouterId "
        "FROM SAFI_LINK_STATE_NODE FINAL WHERE NodeName != ''"
    ):
        name = row["NodeName"].strip().lower()
        if row.get("NodeLocalIgpRouterId"):
            name_by_igp[row["NodeLocalIgpRouterId"]] = name
        if row.get("NodeRouterId") and row.get("NodeLocalIgpRouterId"):
            name_by_router_id[row["NodeRouterId"]] = name
            igp_by_router_id[row["NodeRouterId"]] = row["NodeLocalIgpRouterId"]
    # bgp_ls_links porte les paires RouterId<->IgpRouterId réellement utilisées
    # par les liens (certains RouterId y sont vides, jamais les IgpRouterId).
    for row in ch.query_dicts(
        "SELECT DISTINCT LocalRouterID AS rid, LocalIgpRouterId AS igp FROM bgp_ls_links FINAL "
        "WHERE LocalRouterID != '' AND LocalIgpRouterId != '' "
        "UNION DISTINCT "
        "SELECT DISTINCT RemoteRouterID, RemoteIgpRouterId FROM bgp_ls_links FINAL "
        "WHERE RemoteRouterID != '' AND RemoteIgpRouterId != ''"
    ):
        igp_by_router_id[row["rid"]] = row["igp"]
    return name_by_igp, name_by_router_id, igp_by_router_id


# ── Cycle topologie ─────────────────────────────────────────────────────────

def run_topology_cycle(ch: ClickHouseReader, neo4j: Neo4jClient) -> None:
    """Exécute un cycle complet de synchronisation topologie BGP-LS/SAFI -> Neo4j.
        Les nœuds équipement NetBox existent déjà (Nom insensible à la casse)."""
    # 1) Routers : fusion bgp_ls_nodes (base) + SAFI_LINK_STATE_NODE (overlay,
    # plus riche), puis pose des props BGP sur l'équipement NetBox homonyme.
    routers: dict[str, dict] = {}
    for row in ch.query_dicts("SELECT * FROM bgp_ls_nodes FINAL"):
        rid, props = mapping.router_from_bgp_ls_node(row)
        routers[rid] = mapping.merge_props(routers.get(rid, {}), props)
    for row in ch.query_dicts("SELECT * FROM SAFI_LINK_STATE_NODE FINAL"):
        rid, props = mapping.router_from_safi_node(row)
        routers[rid] = mapping.merge_props(routers.get(rid, {}), props)

    name_by_igp: dict[str, str] = {
        rid: props["Name"].strip().lower()
        for rid, props in routers.items()
        if props.get("Name")
    }
    equip_updates = equip_unmatched = 0
    for rid, props in routers.items():
        name = name_by_igp.get(rid)
        if name and neo4j.update_equipment_bgp(name, {**props, "IgpRouterId": rid}):
            equip_updates += 1
        else:
            equip_unmatched += 1

    # 2) Prefixes : fusion bgp_ls_prefixV4/V6 + SAFI_LINK_STATE_PREFIXE_V4/V6
    prefixes: dict[str, dict] = {}
    announces_prefix: dict[tuple[str, str], dict] = {}
    prefix_sources = [
        ("bgp_ls_prefixV4", "IPv4", mapping.prefix_from_bgp_ls_prefix, mapping.announces_prefix_from_bgp_ls),
        ("bgp_ls_prefixV6", "IPv6", mapping.prefix_from_bgp_ls_prefix, mapping.announces_prefix_from_bgp_ls),
        ("SAFI_LINK_STATE_PREFIXE_V4", "IPv4", mapping.prefix_from_safi_prefix, mapping.announces_prefix_from_safi),
        ("SAFI_LINK_STATE_PREFIXE_V6", "IPv6", mapping.prefix_from_safi_prefix, mapping.announces_prefix_from_safi),
    ]
    for table, family, prefix_fn, announces_fn in prefix_sources:
        for row in ch.query_dicts(f"SELECT * FROM {table} FINAL"):
            pkey, pprops = prefix_fn(row, family)
            prefixes[pkey] = mapping.merge_props(prefixes.get(pkey, {}), pprops)
            rel = announces_fn(row, family)
            if rel is None:
                continue
            igp_router_id, pkey2, rprops = rel
            akey = (igp_router_id, pkey2)
            announces_prefix[akey] = mapping.merge_props(announces_prefix.get(akey, {}), rprops)

    for pkey, props in prefixes.items():
        neo4j.upsert_prefix(pkey, props)
    ann_seen: list[tuple[str, str]] = []
    ann_skipped = 0
    for (igp_router_id, pkey), props in announces_prefix.items():
        name = name_by_igp.get(igp_router_id)
        if name and neo4j.upsert_announces_prefix(name, pkey, props):
            ann_seen.append((name, pkey))
        else:
            ann_skipped += 1
    neo4j.prune_prefixes(prefixes.keys())
    neo4j.prune_announces_prefix(ann_seen)

    # 3) Liens : bgp_ls_links uniquement (les événements monitor_bgp_ls_link ne
    # créent jamais de lien, ils ne posent que Withdraw — voir common/mapping.py)
    links: dict[str, tuple[str, str, dict]] = {}
    for row in ch.query_dicts("SELECT * FROM bgp_ls_links FINAL"):
        res = mapping.adjacent_from_bgp_ls_link(row)
        if res is None:
            continue
        local_igp, remote_igp, key, props = res
        prev = links.get(key)
        links[key] = (local_igp, remote_igp, mapping.merge_props(prev[2] if prev else {}, props))
    link_seen: list[str] = []
    link_skipped = 0
    for key, (local_igp, remote_igp, props) in links.items():
        local_name = name_by_igp.get(local_igp)
        remote_name = name_by_igp.get(remote_igp)
        if local_name and remote_name and neo4j.upsert_adjacent(local_name, remote_name, key, props):
            link_seen.append(key)
        else:
            link_skipped += 1
    neo4j.prune_adjacent(link_seen)

    log.info(
        "Cycle topologie terminé : %d/%d routeur(s) rattachés à un équipement, "
        "%d préfixe(s), %d/%d annonce(s) IGP, %d/%d lien(s) ; "
        "%d routeur(s), %d annonce(s), %d lien(s) sans équipement correspondant.",
        equip_updates, len(routers), len(prefixes),
        len(announces_prefix) - ann_skipped, len(announces_prefix),
        len(links) - link_skipped, len(links),
        equip_unmatched, ann_skipped, link_skipped,
    )


# ── Cycle monitor ────────────────────────────────────────────────────────

def run_monitor_cycle(ch: ClickHouseReader, neo4j: Neo4jClient) -> None:
    """Exécute un cycle de mise à jour des relations existantes à partir des tables monitor_bgp_ls_*
    et monitor_bgp_*."""
    # Fenêtre calculée côté serveur ClickHouse (now()) plutôt que côté client :
    # évite tout écart d'horloge/fuseau entre ce process et le serveur ClickHouse.
    params = {"window": settings.monitor_window_seconds}
    name_by_igp, name_by_router_id, igp_by_router_id = _resolution_maps(ch)

    node_updates = link_updates = prefix_updates = route_upserts = route_skipped = 0

    for row in ch.query_dicts("SELECT * FROM monitor_bgp_ls_node WHERE Age > now() - INTERVAL %(window)s SECOND", params):
        rid, name, withdraw, age = mapping.router_withdraw_from_monitor(row)
        name = name or name_by_igp.get(rid)
        if name and neo4j.update_router_withdraw(name, withdraw, age):
            node_updates += 1

    for row in ch.query_dicts("SELECT * FROM monitor_bgp_ls_link WHERE Age > now() - INTERVAL %(window)s SECOND", params):
        res = mapping.adjacent_withdraw_from_monitor(row)
        if res is None:
            continue
        local_rid, remote_rid, withdraw, age = res
        local_igp = igp_by_router_id.get(local_rid)
        remote_igp = igp_by_router_id.get(remote_rid)
        if not local_igp or not remote_igp:
            continue
        key = mapping.link_key(local_igp, remote_igp)
        if neo4j.update_adjacent_withdraw(key, withdraw, age):
            link_updates += 1

    for table, family in (("monitor_bgp_ls_prefixev4", "IPv4"), ("monitor_bgp_ls_prefixev6", "IPv6")):
        for row in ch.query_dicts(f"SELECT * FROM {table} WHERE Age > now() - INTERVAL %(window)s SECOND", params):
            res = mapping.announces_prefix_withdraw_from_monitor(row, family)
            if res is None:
                continue
            igp_router_id, pkey, withdraw, age = res
            name = name_by_igp.get(igp_router_id)
            if name and neo4j.update_announces_prefix_withdraw(name, pkey, withdraw, age):
                prefix_updates += 1

    route_sources = [
        ("monitor_bgp_ipv4unicast", mapping.announces_route_from_ipv4unicast),
        ("monitor_bgp_lu", mapping.announces_route_from_lu),
        ("monitor_bgp_vpn", mapping.announces_route_from_vpn),
    ]
    for table, fn in route_sources:
        for row in ch.query_dicts(f"SELECT * FROM {table} WHERE Age > now() - INTERVAL %(window)s SECOND", params):
            res = fn(row)
            if res is None:
                continue
            router_id, pkey, family_label, props = res
            name = name_by_router_id.get(router_id)
            if not name:
                route_skipped += 1
                continue
            prefix_family, prefix_value = pkey.split("|", 1)
            prefix_props = {"Key": pkey, "Prefix": prefix_value, "Family": prefix_family}
            if neo4j.upsert_announces_route(name, pkey, prefix_props, family_label, props):
                route_upserts += 1
            else:
                route_skipped += 1

    log.info(
        "Cycle monitor terminé : %d routeur(s), %d lien(s), %d annonce(s) IGP mis à jour ; "
        "%d annonce(s) BGP classique créée(s)/mise(s) à jour, %d ignorée(s) (équipement introuvable).",
        node_updates, link_updates, prefix_updates, route_upserts, route_skipped,
    )


# ── Boucles ──────────────────────────────────────────────────────────────

def _loop(name: str, interval: int, fn) -> None:
    ch = ClickHouseReader()
    neo4j = Neo4jClient()
    try:
        while _running.is_set():
            try:
                fn(ch, neo4j)
            except Exception:  # noqa: BLE001
                log.exception("Boucle %s : échec du cycle ; nouvelle tentative au prochain intervalle.", name)
            for _ in range(interval):
                if not _running.is_set():
                    break
                time.sleep(1)
    finally:
        ch.close()
        neo4j.close()
        log.info("Boucle %s arrêtée proprement.", name)


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    bootstrap_neo4j = Neo4jClient()
    bootstrap_neo4j.ensure_constraints()
    bootstrap_neo4j.close()

    log.info(
        "Reconciler démarré (ClickHouse=%s:%d/%s, Neo4j=%s, topologie=%ds, monitor=%ds/%ds).",
        settings.clickhouse_host, settings.clickhouse_port, settings.clickhouse_database,
        settings.neo4j_uri, settings.reconcile_interval_seconds,
        settings.monitor_poll_interval_seconds, settings.monitor_window_seconds,
    )

    threads = [
        threading.Thread(
            target=_loop, name="topology",
            args=("topologie", settings.reconcile_interval_seconds, run_topology_cycle),
            daemon=True,
        ),
        threading.Thread(
            target=_loop, name="monitor",
            args=("monitor", settings.monitor_poll_interval_seconds, run_monitor_cycle),
            daemon=True,
        ),
    ]
    for t in threads:
        t.start()

    while _running.is_set():
        time.sleep(1)
    for t in threads:
        t.join(timeout=30)
    log.info("Reconciler arrêté proprement.")


if __name__ == "__main__":
    main()

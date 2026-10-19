"""Traduction lignes ClickHouse (gobgp) -> entités du graphe Neo4j.

Le graphe ne contient PAS de nœud Router : les routeurs BGP-LS sont rattachés
aux nœuds équipement NetBox existants par leur nom (`Nom`, match insensible à
la casse). Les fonctions de ce module continuent d'identifier les routeurs par
IgpRouterId/RouterId ; la résolution identifiant -> nom d'équipement est faite
par le reconciler à partir des tables nœuds.

Deux générations de collecte cohabitent dans ClickHouse pour la même réalité
(routeurs/ISIS/ANNOUNCES_PREFIX) : `bgp_ls_*` (pull historique, champs
`LocalRouterID`/`IgpRouter`...) et `SAFI_LINK_STATE_*` (pull plus riche, champs
`Withdraw`/`Best`/`NodeRouterId`...). Les deux sont consolidées en un seul jeu de
propriétés par entité (voir `merge_props`) avant upsert, plutôt que d'écraser
l'une avec l'autre à chaque cycle.

Les tables `monitor_bgp_ls_*` (flux d'événements Vector, append-only) partagent
les mêmes clés d'identité que `SAFI_LINK_STATE_*` — sauf `monitor_bgp_ls_link`
qui n'a pas `LinkLocalIgpRouterId` (incohérence du schéma amont).

ISIS ne provient QUE de `bgp_ls_links` (liens BGP-LS du pull) ; les
événements `monitor_bgp_ls_link` ne créent jamais de lien, ils posent uniquement
`Withdraw`/`LastEventAge` sur le lien existant. La clé est
`LocalIgpRouterId|RemoteIgpRouterId` : les RouterId (loopback) sont parfois
vides dans `bgp_ls_links` (routeurs UCS), ce qui rendrait la clé dégénérée et
ferait entrer en collision les liens de plusieurs routeurs. Le flux monitor ne
portant que les RouterId, le reconciler les résout en IgpRouterId via les
paires RouterId<->IgpRouterId de `bgp_ls_links` (voir `_resolution_maps`).
Pas d'identifiants d'interface dans la clé : `bgp_ls_links` ne les expose pas
et le flux monitor les remonte toujours à 0.
"""

from __future__ import annotations

from typing import Any


def _bool(value: Any) -> bool:
    """Convertit une valeur en booléen, avec tolérance sur les chaînes 'true'/'false'."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _clean_prefix(value: str) -> str:
    """`IpReachability`/`PrefixeIpReachability` sont formatés `[a.b.c.d/nn]`
    (quirk du pull GoBGP) : on retire les crochets pour une valeur CIDR propre."""
    return value.strip("[]") if value else value


def merge_props(base: dict, overlay: dict) -> dict:
    """Fusionne overlay sur base ; ignore les valeurs vides/None d'overlay
    (évite qu'une source moins complète efface un champ déjà connu)."""
    merged = dict(base)
    for k, v in overlay.items():
        if v is not None and v != "":
            merged[k] = v
    return merged


# ── Router (nœud) ─────────────────────────────────────────────────────────

def router_from_bgp_ls_node(row: dict) -> tuple[str, dict]:
    """Retourne (igp_router_id, props) à partir d'une ligne bgp_ls_nodes."""
    igp_router_id = row["IgpRouter"]
    props = {
        "Name": row.get("Node"),
        "Asn": row.get("Asn"),
        "Overload": _bool(row.get("overload")),
        "BgpLsId": row.get("BgpLsId"),
        "LastSeen": row.get("Age"),
    }
    return igp_router_id, props


def router_from_safi_node(row: dict) -> tuple[str, dict]:
    """Retourne (igp_router_id, props) à partir d'une ligne SAFI_LINK_STATE_NODES."""
    igp_router_id = row["NodeLocalIgpRouterId"]
    props = {
        "Name": row.get("NodeName"),
        "Asn": row.get("Asn"),
        "RouterId": row.get("NodeRouterId") or None,
        "IsisArea": row.get("NodeIsisArea"),
        "Overload": _bool(row.get("NodeOverload")),
        "Protocol": row.get("ProtocolID"),
        "Withdraw": _bool(row.get("Withdraw")),
        "BgpLsId": row.get("NodeLocalBgpLsId"),
        "LastSeen": row.get("Age"),
    }
    return igp_router_id, props


def router_withdraw_from_monitor(row: dict) -> tuple[str, str, bool, Any]:
    """Retourne (igp_router_id, nom normalisé ou '', withdraw, age) ; le nom
    peut manquer dans le flux monitor, le reconciler retombe alors sur la
    résolution IgpRouterId -> nom construite depuis les tables d'état."""
    name = (row.get("NodeName") or "").strip().lower()
    return row["NodeLocalIgpRouterId"], name, _bool(row.get("Withdraw")), row.get("Age")


# ── ISIS (relation Router -> Router) ─────────────────────────────────

def link_key(local_igp_router_id: str, remote_igp_router_id: str) -> str:
    """Retourne la clé unique d'un lien BGP-LS/ISIS : `LocalIgpRouterId|RemoteIgpRouterId`."""
    return f"{local_igp_router_id}|{remote_igp_router_id}"


def adjacent_from_bgp_ls_link(row: dict) -> tuple[str, str, str, dict] | None:
    """Retourne (local_router_id, remote_router_id, key, props) à partir d'une
    ligne bgp_ls_links. Les RouterId sont à résoudre en IgpRouterId pour
    reconstituer la clé du lien."""
    local_igp = row.get("LocalIgpRouterId")
    remote_igp = row.get("RemoteIgpRouterId")

    if not local_igp or not remote_igp:
        return None

    key = link_key(local_igp, remote_igp)
    props = {
        "IgpMetric": row.get("IgpMetric"),
        "BgpLsId": row.get("BgpLsId"),
        "LastSeen": row.get("Age"),
    }
    return local_igp, remote_igp, key, props


def adjacent_withdraw_from_monitor(row: dict) -> tuple[str, str, bool, Any] | None:
    """Retourne (local_router_id, remote_router_id, withdraw, age) ; les
    RouterId sont à résoudre en IgpRouterId pour reconstituer la clé du lien."""
    local = row.get("LinkLocalRouterId")
    remote = row.get("LinkRemoteRouterId")
    if not local or not remote:
        return None
    return local, remote, _bool(row.get("Withdraw")), row.get("Age")


# ── Prefix (nœud) ────────────────────────────────────────────────────────

def prefix_key(family: str, prefix: str) -> str:
    """Retourne la clé unique d'un préfixe : `Family|Prefix`."""
    return f"{family}|{prefix}"


def prefix_from_bgp_ls_prefix(row: dict, family: str) -> tuple[str, dict]:
    """Retourne (key, props) à partir d'une ligne bgp_ls_prefixes."""
    prefix = _clean_prefix(row["IpReachability"])
    key = prefix_key(family, prefix)
    props = {
        "Prefix": prefix,
        "Family": family,
        "BgpLsId": row.get("BgpLsId"),
        "LastSeen": row.get("Age"),
    }
    return key, props


def prefix_from_safi_prefix(row: dict, family: str) -> tuple[str, dict]:
    """Retourne (key, props) à partir d'une ligne SAFI_LINK_STATE_PREFIXES."""
    prefix = _clean_prefix(row["PrefixeIpReachability"])
    key = prefix_key(family, prefix)
    props = {
        "Prefix": prefix,
        "Family": family,
        "OspfRouteType": row.get("PrefixeOspfRouteType"),
        "Withdraw": _bool(row.get("Withdraw")),
        "LastSeen": row.get("Age"),
    }
    return key, props


# ── ANNOUNCES_PREFIX (relation Router -> Prefix, réseau IGP) ───────────────

def announces_prefix_from_bgp_ls(row: dict, family: str) -> tuple[str, str, dict] | None:
    """Retourne (igp_router_id, key, props) à partir d'une ligne bgp_ls_prefixes."""
    igp_router_id = row.get("IgpRouterID")
    if not igp_router_id:
        return None
    pkey = prefix_key(family, _clean_prefix(row["IpReachability"]))
    props = {"LastSeen": row.get("Age")}
    return igp_router_id, pkey, props


def announces_prefix_from_safi(row: dict, family: str) -> tuple[str, str, dict] | None:
    """Retourne (igp_router_id, key, props) à partir d'une ligne SAFI_LINK_STATE_PREFIXES."""
    igp_router_id = row.get("PrefixeLocalIgpRouterId")
    if not igp_router_id:
        return None
    pkey = prefix_key(family, _clean_prefix(row["PrefixeIpReachability"]))
    props = {"Withdraw": _bool(row.get("Withdraw")), "LastSeen": row.get("Age")}
    return igp_router_id, pkey, props


def announces_prefix_withdraw_from_monitor(row: dict, family: str) -> tuple[str, str, bool, Any] | None:
    """Retourne (igp_router_id, key, withdraw, age) à partir d'une ligne de monitoring."""
    igp_router_id = row.get("PrefixeLocalIgpRouterId")
    if not igp_router_id:
        return None
    pkey = prefix_key(family, _clean_prefix(row["PrefixeIpReachability"]))
    return igp_router_id, pkey, _bool(row.get("Withdraw")), row.get("Age")


# ── ANNOUNCES_ROUTE (relation Router -> Prefix, BGP classique) ─────────────
# Le Router est retrouvé via OriginatorId (BGP) = RouterId (BGP-LS), pas via
# IgpRouterId : ces tables n'exposent que NeighborIp/SourceId (session BGP vers
# le collecteur, constante), pas l'identité IGP du routeur d'origine.

def announces_route_from_ipv4unicast(row: dict) -> tuple[str, str, str, dict] | None:
    """Retourne (originator_id, key, SAFI, props) à partir d'une ligne ANNOUNCES_PREFIX."""
    originator_id = row.get("OriginatorId")
    if not originator_id:
        return None
    pkey = prefix_key("IPv4", f"{row['Prefix']}/{row['PrefixLen']}")
    props = {
        "AsPath": row.get("AsPath"),
        "LocalPref": row.get("LocalPref"),
        "Med": row.get("Med"),
        "NextHops": row.get("NextHops"),
        "Withdraw": _bool(row.get("Withdraw")),
        "LastSeen": row.get("Age"),
    }
    return originator_id, pkey, "ipv4unicast", props


def announces_route_from_lu(row: dict) -> tuple[str, str, str, dict] | None:
    """Retourne (originator_id, key, SAFI, props) à partir d'une ligne ANNOUNCES_PREFIX."""
    originator_id = row.get("OriginatorId")
    if not originator_id:
        return None
    pkey = prefix_key("IPv4", f"{row['Prefix']}/{row['PrefixLen']}")
    props = {
        "AsPath": row.get("AsPath"),
        "Label": row.get("Label"),
        "LocalPref": row.get("LocalPref"),
        "Withdraw": _bool(row.get("Withdraw")),
        "LastSeen": row.get("Age"),
    }
    return originator_id, pkey, "labeled_unicast", props


def announces_route_from_vpn(row: dict) -> tuple[str, str, str, dict] | None:
    """Retourne (originator_id, key, SAFI, props) à partir d'une ligne ANNOUNCES_PREFIX."""
    originator_id = row.get("OriginatorId")
    if not originator_id:
        return None
    pkey = prefix_key("VPNv4", f"{row['Prefix']}/{row['PrefixLen']}")
    props = {
        "AsPath": row.get("AsPath"),
        "RdAdmin": row.get("RdAdmin"),
        "RdAssigned": row.get("RdAssigned"),
        "LocalPref": row.get("LocalPref"),
        "Withdraw": _bool(row.get("Withdraw")),
        "LastSeen": row.get("Age"),
    }
    return originator_id, pkey, "vpn", props

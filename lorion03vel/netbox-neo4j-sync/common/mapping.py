"""Mapping NetBox → graphe Neo4j (modèle dénormalisé).

Modèle :
- 1 nœud par device, **label = rôle feuille** (:spinebib, :pesms, ...).
- Propriétés métier dénormalisées (Nom, Role, Fonction, Manufacturer, Chassis,
  Site, Rack, Position, Face, Entite, LastUpdate, ConsolePorts, Loopback*).
- Relation `(a)-[:EST_CONNECTE_A {…}]->(b)` : une par câble entre deux devices.

Source unique réutilisée par le reconciler (balayage complet) et le receiver
(resync ciblé sur webhook).
"""

from __future__ import annotations

from typing import Callable, Iterable

from common.config import settings
from common.logging import get_logger
from common.neo4j_client import Neo4jClient, sanitize_label
from common.netbox_client import NetBoxClient

log = get_logger("mapping")


# ── Hiérarchie des rôles (pour Fonction = rôle racine) ──────────────────
class RoleHierarchy:
    def __init__(self, roles: list[dict]) -> None:
        self._by_id: dict[int, tuple[str, int | None]] = {}
        for r in roles:
            parent = r.get("parent")
            pid = parent.get("id") if isinstance(parent, dict) else None
            self._by_id[r["id"]] = (r.get("name"), pid)

    def name(self, role_id: int | None) -> str | None:
        """Retourne le nom du rôle ou None si inconnu."""
        return self._by_id.get(role_id, (None, None))[0] if role_id is not None else None

    def root_name(self, role_id: int | None) -> str | None:
        """Remonte la chaîne des parents jusqu'à la racine (= Fonction)."""
        cur = role_id
        seen: set[int] = set()
        last: str | None = self.name(role_id)
        while cur is not None and cur not in seen:
            seen.add(cur)
            nm, pid = self._by_id.get(cur, (None, None))
            last = nm if nm is not None else last
            if pid is None:
                return nm
            cur = pid
        return last

    def all_names(self) -> list[str]:
        return [n for (n, _) in self._by_id.values() if n]


def build_role_hierarchy(netbox: NetBoxClient) -> RoleHierarchy:
    """ Construit la hiérarchie des rôles à partir de l'API NetBox. Retourne un objet RoleHierarchy."""
    return RoleHierarchy(list(netbox.iter_objects("/api/dcim/device-roles/")))


# ── Helpers d'extraction ────────────────────────────────────────────────
def _nested(d: dict | None, *keys: str):
    """Retourne d[k1][k2]… ou None si une clé est absente ou si d n'est pas un dict."""
    if d is None:
        return None

    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _clean(props: dict) -> dict:
    """Supprime les clés dont la valeur est None."""
    return {k: v for k, v in props.items() if v is not None}


def _ip_device_id(ip: dict) -> int | None:
    """Retourne l'id du device auquel est assignée l'IP, ou None si non applicable."""
    return _nested(ip, "assigned_object", "device", "id")


def _iface_device_id(iface: dict) -> int | None:
    """Retourne l'id du device à qui appartient l'interface, ou None si non applicable."""
    return _nested(iface, "device", "id")


def _console_device_id(cp: dict) -> int | None:
    """Retourne l'id du device à qui appartient le port console, ou None si non applicable."""
    return _nested(cp, "device", "id")


def group_by(items: Iterable[dict], key: Callable[[dict], int | None]) -> dict[int, list[dict]]:
    """Groupe les items par clé. Les items dont la clé est None sont ignorés."""
    out: dict[int, list[dict]] = {}
    for it in items:
        k = key(it)
        if k is not None:
            out.setdefault(k, []).append(it)
    return out


# ── Construction des propriétés d'un device ─────────────────────────────
def device_props(
    device: dict,
    roles: RoleHierarchy,
    ips: list[dict],
    consoles: list[dict],
) -> tuple[str, int, dict] | None:
    """Retourne (role_label, device_id, props) ou None si le device n'a pas de rôle."""
    role_id = _nested(device, "role", "id")
    role_name = _nested(device, "role", "name")
    if not role_name:
        log.warning("Device %s sans rôle : ignoré", device.get("id"))
        return None

    props = _clean({
        "Id": device["id"],
        "Nom": device.get("name"),
        "Role": role_name,
        "Fonction": roles.root_name(role_id),
        "Manufacturer": _nested(device, "device_type", "manufacturer", "name"),
        "Chassis": _nested(device, "device_type", "model"),
        "Site": _nested(device, "site", "id"),
        "Rack": _nested(device, "rack", "name"),
        "Position": device.get("position"),
        "Face": _nested(device, "face", "label"),
        "Entite": _nested(device, "tenant", "name"),
        "LastUpdate": device.get("last_updated"),
    })

    # ConsolePorts : "NOM (label_cable)" ou "NOM" si pas de câble.
    cports = []
    for cp in consoles:
        label = _nested(cp, "cable", "label")
        cports.append(f"{cp.get('name')} ({label})" if label else str(cp.get("name")))
    if cports:
        props["ConsolePorts"] = cports

    # Loopback* : une propriété par interface nommée Loopback*, valeur = son IP.
    for ip in ips:
        iface_name = _nested(ip, "assigned_object", "name")
        if iface_name and iface_name.lower().startswith("loopback") and ip.get("address"):
            props[iface_name] = ip["address"]

    props["Id"] = device["id"]  # garantit la présence de la clé après _clean
    return sanitize_label(role_name), device["id"], props


# ── Construction d'une relation de câble ────────────────────────────────
def _iface_ids(terminations) -> list[int]:
    """Retourne la liste des ids d'interfaces des terminaisons du câble."""
    ids = []
    for t in terminations or []:
        if isinstance(t, dict) and t.get("object_type") == "dcim.interface":
            oid = t.get("object_id") or _nested(t, "object", "id")
            if oid is not None:
                ids.append(oid)
    return ids


def cable_rel(cable: dict, iface_index: dict[int, dict]) -> tuple[int, int, str, dict] | None:
    """Retourne (a_device_id, b_device_id, cable_name, props) ou None si non applicable
    (câble sans deux terminaisons d'interface connues)."""
    a_ids = _iface_ids(cable.get("a_terminations"))
    b_ids = _iface_ids(cable.get("b_terminations"))
    if not a_ids or not b_ids:
        return None
    a = iface_index.get(a_ids[0])
    b = iface_index.get(b_ids[0])
    if not a or not b:
        return None
    a_dev = _iface_device_id(a)
    b_dev = _iface_device_id(b)
    if a_dev is None or b_dev is None:
        return None

    cable_name = cable.get("label") or f"cable-{cable['id']}"
    props = _clean({
        "CableName": cable_name,
        "Source": _nested(a, "device", "name"),
        "Destination": _nested(b, "device", "name"),
        "LocalPortName": a.get("name"),
        "RemoteDevicePort": b.get("name"),
        "InterfaceId": a.get("id"),
        "RemoteDeviceId": b_dev,
        "Lag": _nested(a, "lag", "name"),
        "Status": "Enabled" if a.get("enabled") else "Disabled",
    })
    return a_dev, b_dev, cable_name, props


# ── Resync ciblé (utilisé par le receiver) ──────────────────────────────
def resync_device(netbox: NetBoxClient, neo4j: Neo4jClient, device_id: int, roles: RoleHierarchy) -> None:
    """Récupère le device, ses IPs et ses ports console, et met à jour le nœud dans Neo4j."""
    device = netbox.get_object(f"/api/dcim/devices/{device_id}/")
    ips = list(netbox.iter_objects(f"/api/ipam/ip-addresses/?device_id={device_id}"))
    consoles = list(netbox.iter_objects(f"/api/dcim/console-ports/?device_id={device_id}"))
    res = device_props(device, roles, ips, consoles)
    if res:
        neo4j.upsert_device(*res)
        neo4j.link_device_to_site(device["id"], settings.site_nom)


def resync_cable(netbox: NetBoxClient, neo4j: Neo4jClient, cable: dict) -> None:
    """Récupère les interfaces des terminaisons du câble et met à jour la relation EST_CONNECTE_A dans Neo4j."""
    # Enrichit les interfaces des terminaisons (lag/enabled non fournis dans le câble).
    ids = _iface_ids(cable.get("a_terminations")) + _iface_ids(cable.get("b_terminations"))
    index = {i: netbox.get_object(f"/api/dcim/interfaces/{i}/") for i in ids}
    rel = cable_rel(cable, index)
    if rel:
        neo4j.upsert_connected(*rel)
    else:
        neo4j.delete_connected(cable.get("label") or f"cable-{cable['id']}")


# ── Dispatch webhook ────────────────────────────────────────────────────
def apply_webhook(netbox, neo4j, roles: RoleHierarchy, model: str, data: dict) -> bool:
    """created/updated. Retourne False si le modèle est hors périmètre."""
    if model == "device":
        resync_device(netbox, neo4j, data["id"], roles)
    elif model in {"interface", "consoleport"}:
        dev_id = _nested(data, "device", "id")
        if dev_id:
            resync_device(netbox, neo4j, dev_id, roles)
    elif model == "ipaddress":
        dev_id = _ip_device_id(data)
        if dev_id:
            resync_device(netbox, neo4j, dev_id, roles)
    elif model == "cable":
        resync_cable(netbox, neo4j, data)
    else:
        return False
    return True


def delete_webhook(netbox, neo4j, roles: RoleHierarchy, model: str, data: dict) -> bool:
    """deleted. Retourne False si hors périmètre."""
    if model == "device":
        neo4j.delete_device(data["id"])
    elif model == "cable":
        neo4j.delete_connected(data.get("label") or f"cable-{data['id']}")
    elif model in {"interface", "consoleport"}:
        # Sous-objet supprimé : on rafraîchit le nœud device s'il existe encore.
        dev_id = _nested(data, "device", "id")
        if dev_id:
            resync_device(netbox, neo4j, dev_id, roles)
    elif model == "ipaddress":
        dev_id = _ip_device_id(data)
        if dev_id:
            resync_device(netbox, neo4j, dev_id, roles)
    else:
        return False
    return True

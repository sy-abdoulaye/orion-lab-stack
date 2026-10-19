"""CLI d'administration netbox-neo4j-sync.

Automatise la configuration NetBox (Webhook + Event Rule) et la gestion Neo4j
(initialisation/full-sync, purge, stats, suppression ciblée).

Exécution (réutilise le service reconciler : mêmes .env et réseaux) :
    docker compose run --rm reconciler python -m admin <commande> [options]

Commandes :
    stats                 Affiche les compteurs du graphe (labels, nœuds, relations).
    init                  Synchronisation complète immédiate NetBox -> Neo4j (bootstrap).
    wipe [--drop-constraints] [--yes]
                          Supprime tous les nœuds/relations (et contraintes si demandé).
    delete-device --id N  Supprime le nœud device d'Id N.
    setup-webhooks [--url U] [--name NAME]
                          Crée/met à jour le Webhook + l'Event Rule NetBox (idempotent).
    teardown-webhooks [--name NAME]
                          Supprime le Webhook + l'Event Rule NetBox.
"""

from __future__ import annotations

import argparse
import sys

from common.config import settings
from common.logging import get_logger
from common.netbox_client import NetBoxClient
from common.neo4j_client import Neo4jClient

log = get_logger("admin")

# Nom canonique du webhook / de l'event rule gérés par ce CLI.
DEFAULT_NAME = "neo4j-sync"
# URL du receiver, joignable par NetBox sur le réseau lorion03vel-network.
DEFAULT_WEBHOOK_URL = "http://netbox-neo4j-sync-receiver:8000/webhook"
# Types d'objets NetBox déclenchant la synchro (périmètre du modèle).
OBJECT_TYPES = [
    "dcim.device",
    "dcim.interface",
    "dcim.consoleport",
    "ipam.ipaddress",
    "dcim.cable",
    "dcim.devicerole",
]
EVENT_TYPES = ["object_created", "object_updated", "object_deleted"]


# ── Neo4j ───────────────────────────────────────────────────────────────
def cmd_stats(_args) -> None:
    """Affiche les compteurs du graphe Neo4j : nœuds, relations EST_CONNECTE_A, labels."""
    neo4j = Neo4jClient()
    try:
        c = neo4j.counts()
    finally:
        neo4j.close()
    print(f"Nœuds        : {c['nodes']}")
    print(f"EST_CONNECTE_A : {c['connected']}")
    print(f"Rôles/labels ({len(c['labels'])}) : {', '.join(c['labels']) or '(aucun)'}")


def cmd_init(_args) -> None:
    """Synchronisation complète immédiate NetBox -> Neo4j (bootstrap)."""
    # Import tardif pour éviter une dépendance circulaire au chargement.
    from reconciler.main import run_once

    netbox = NetBoxClient()
    neo4j = Neo4jClient()
    try:
        log.info("Initialisation/full-sync depuis NetBox…")
        run_once(netbox, neo4j)
    finally:
        netbox.close()
        neo4j.close()


def cmd_wipe(args) -> None:
    """Supprime tous les nœuds/relations du graphe Neo4j (et contraintes si demandé)."""
    if not args.yes:
        reply = input("Supprimer TOUS les nœuds/relations du graphe ? [y/N] ").strip().lower()
        if reply != "y":
            print("Annulé.")
            return
    neo4j = Neo4jClient()
    try:
        deleted = neo4j.wipe_all(drop_constraints=args.drop_constraints)
    finally:
        neo4j.close()
    print(f"{deleted} nœud(s) supprimé(s)" + (" + contraintes" if args.drop_constraints else ""))


def cmd_delete_device(args) -> None:
    """Supprime le nœud device d'Id args.id (s'il existe)."""
    neo4j = Neo4jClient()
    try:
        neo4j.delete_device(args.id)
    finally:
        neo4j.close()
    print(f"Device Id={args.id} supprimé (s'il existait).")


# ── NetBox (webhook + event rule) ───────────────────────────────────────
def _upsert(netbox: NetBoxClient, path: str, name: str, payload: dict) -> dict:
    """Crée ou met à jour un objet NetBox (webhook ou event rule) par nom."""
    existing = netbox.list_objects(path, name=name)
    if existing:
        obj = netbox.patch(f"{path}{existing[0]['id']}/", payload)
        log.info("Mis à jour: %s#%s", path, obj["id"])
    else:
        obj = netbox.create(path, payload)
        log.info("Créé: %s#%s", path, obj["id"])
    return obj


def cmd_setup_webhooks(args) -> None:
    """Crée ou met à jour le Webhook + l'Event Rule NetBox (idempotent)."""
    if not settings.webhook_secret:
        log.warning("WEBHOOK_SECRET vide : le webhook sera créé sans signature (déconseillé).")
    netbox = NetBoxClient()
    try:
        webhook = _upsert(netbox, "/api/extras/webhooks/", args.name, {
            "name": args.name,
            "payload_url": args.url,
            "http_method": "POST",
            "http_content_type": "application/json",
            "ssl_verification": False,  # receiver en HTTP interne
            "secret": settings.webhook_secret,
        })
        _upsert(netbox, "/api/extras/event-rules/", args.name, {
            "name": args.name,
            "enabled": True,
            "object_types": OBJECT_TYPES,
            "event_types": EVENT_TYPES,
            "action_type": "webhook",
            "action_object_type": "extras.webhook",
            "action_object_id": webhook["id"],
        })
    finally:
        netbox.close()
    print(f"Webhook + Event Rule '{args.name}' configurés → {args.url}")
    print(f"  object_types : {', '.join(OBJECT_TYPES)}")


def cmd_teardown_webhooks(args) -> None:
    """Supprime le Webhook + l'Event Rule NetBox (s'ils existent)."""
    netbox = NetBoxClient()
    try:
        for path in ("/api/extras/event-rules/", "/api/extras/webhooks/"):
            for obj in netbox.list_objects(path, name=args.name):
                netbox.remove(f"{path}{obj['id']}/")
                log.info("Supprimé: %s#%s", path, obj["id"])
    finally:
        netbox.close()
    print(f"Webhook + Event Rule '{args.name}' supprimés.")


# ── Parsing ─────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    """Construit le parser d'arguments pour le CLI d'administration."""
    p = argparse.ArgumentParser(prog="python -m admin", description="Admin netbox-neo4j-sync")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="Compteurs du graphe").set_defaults(func=cmd_stats)
    sub.add_parser("init", help="Full-sync immédiat NetBox->Neo4j").set_defaults(func=cmd_init)

    w = sub.add_parser("wipe", help="Purge le graphe")
    w.add_argument("--drop-constraints", action="store_true", help="Supprime aussi les contraintes")
    w.add_argument("--yes", action="store_true", help="Sans confirmation")
    w.set_defaults(func=cmd_wipe)

    d = sub.add_parser("delete-device", help="Supprime un device par Id")
    d.add_argument("--id", type=int, required=True)
    d.set_defaults(func=cmd_delete_device)

    s = sub.add_parser("setup-webhooks", help="Crée/MAJ le Webhook + Event Rule NetBox")
    s.add_argument("--url", default=DEFAULT_WEBHOOK_URL)
    s.add_argument("--name", default=DEFAULT_NAME)
    s.set_defaults(func=cmd_setup_webhooks)

    t = sub.add_parser("teardown-webhooks", help="Supprime le Webhook + Event Rule NetBox")
    t.add_argument("--name", default=DEFAULT_NAME)
    t.set_defaults(func=cmd_teardown_webhooks)

    return p


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du CLI d'administration netbox-neo4j-sync."""
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.error("Échec: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

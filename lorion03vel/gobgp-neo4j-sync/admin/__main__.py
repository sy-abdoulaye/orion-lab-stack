"""CLI d'administration gobgp-neo4j-sync.

Exécution (réutilise le service reconciler : mêmes .env et réseaux) :
    docker compose run --rm reconciler python -m admin <commande>

Commandes :
    stats   Affiche les compteurs du graphe (nœuds par label, relations par type).
    init    Synchronisation complète immédiate ClickHouse -> Neo4j (cycle topologie
            + un cycle monitor sur la fenêtre configurée).
    wipe [--yes]
            Supprime les données de CETTE synchro : relations ISIS/
            ANNOUNCES_PREFIX/ANNOUNCES_ROUTE, nœuds Prefix, et propriétés BGP
            posées sur les nœuds équipement (Asn, IgpRouterId, Withdraw...).
            Ne supprime pas les nœuds équipement gérés par netbox-neo4j-sync.
"""

from __future__ import annotations

import argparse
import sys

from common.clickhouse_client import ClickHouseReader
from common.logging import get_logger
from common.neo4j_client import Neo4jClient
from reconciler.main import run_monitor_cycle, run_topology_cycle

log = get_logger("admin")


def cmd_stats(neo4j: Neo4jClient) -> None:
    counts = neo4j.counts()
    print("Nœuds :")
    for label, c in sorted(counts["nodes"].items()):
        print(f"  {label:<20} {c}")
    print("Relations :")
    for rel_type, c in sorted(counts["relationships"].items()):
        print(f"  {rel_type:<20} {c}")


def cmd_init(ch: ClickHouseReader, neo4j: Neo4jClient) -> None:
    neo4j.ensure_constraints()
    run_topology_cycle(ch, neo4j)
    run_monitor_cycle(ch, neo4j)


def cmd_wipe(neo4j: Neo4jClient, yes: bool) -> None:
    if not yes:
        confirm = input(
            "Supprimer les relations BGP, les nœuds Prefix et les propriétés "
            "BGP des équipements ? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Annulé.")
            return
    neo4j.wipe_all()


def main() -> None:
    parser = argparse.ArgumentParser(prog="admin")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stats")
    sub.add_parser("init")
    wipe_parser = sub.add_parser("wipe")
    wipe_parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    neo4j = Neo4jClient()
    try:
        if args.command == "stats":
            cmd_stats(neo4j)
        elif args.command == "init":
            ch = ClickHouseReader()
            try:
                cmd_init(ch, neo4j)
            finally:
                ch.close()
        elif args.command == "wipe":
            cmd_wipe(neo4j, args.yes)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        neo4j.close()


if __name__ == "__main__":
    main()

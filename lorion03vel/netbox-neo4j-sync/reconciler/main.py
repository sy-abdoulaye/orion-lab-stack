""" Réconciliateur principal : synchronisation NetBox → Neo4j.

    Ce script est conçu pour être exécuté comme un processus de longue durée
    (par exemple via docker-compose).

    Il récupère périodiquement la liste des équipements et des câbles depuis NetBox,
    puis met à jour le graphe Neo4j en conséquence. Il supprime également de Neo4j
    les équipements ou les câbles qui n'existent plus dans NetBox.

    L'intervalle de réconciliation est configurable via la variable d'environnement
    RECONCILE_INTERVAL_SECONDS.

    Le réconciliateur peut être arrêté proprement en envoyant un signal SIGTERM ou
    SIGINT. Dans ce cas, il termine le cycle en cours puis se ferme.

    La journalisation (logging) est configurée via le module common.logging et
    s'effectue sur la sortie standard (stdout). Le niveau de journalisation peut être
    défini via la variable d'environnement LOG_LEVEL.

    Le réconciliateur utilise les classes :
    - common.netbox_client.NetBoxClient
    - common.neo4j_client.Neo4jClient

    pour interagir respectivement avec NetBox et Neo4j. Ces clients gèrent
    l'authentification, la gestion des connexions et les requêtes API.

    Le réconciliateur construit également une hiérarchie des rôles à partir de NetBox
    en utilisant la fonction common.mapping.build_role_hierarchy. Cette hiérarchie
    est utilisée pour déterminer les rôles des équipements lors de la création ou
    de la mise à jour des nœuds dans Neo4j.

    Le réconciliateur garantit que les contraintes nécessaires sont présentes dans
    Neo4j pour les rôles des équipements. Il utilise le module common.mapping pour
    convertir les objets NetBox en nœuds et relations Neo4j.

    À chaque cycle, le réconciliateur journalise le nombre d'équipements et de
    relations traités, ainsi que les éventuelles erreurs rencontrées pendant le
    processus de réconciliation.

    Si une erreur survient, l'exception est enregistrée dans les logs, puis le
    réconciliateur poursuit son exécution et attend l'intervalle configuré avant
    de lancer le cycle suivant.

    Le réconciliateur peut être exécuté dans un conteneur Docker. Il est recommandé
    d'utiliser la configuration docker-compose fournie afin de mettre en place
    l'environnement et les dépendances nécessaires.

    Le réconciliateur se connectera automatiquement aux services Neo4j et NetBox
    définis dans la configuration docker-compose.

    Le réconciliateur est conçu pour être idempotent, ce qui signifie que son
    exécution plusieurs fois ne créera pas de doublons de nœuds ou de relations
    dans Neo4j.

    En cas de réception d'un événement webhook provenant de NetBox, le
    réconciliateur peut être déclenché afin de resynchroniser le ou les équipements
    concernés en effectuant une nouvelle interrogation de l'API NetBox.

    Cela permet d'obtenir des mises à jour quasi temps réel du graphe Neo4j lorsque
    des modifications sont effectuées dans NetBox, sans attendre le prochain cycle
    de réconciliation planifié.
"""
from __future__ import annotations

import signal
import time

from common import mapping
from common.config import settings
from common.logging import get_logger
from common.netbox_client import NetBoxClient
from common.neo4j_client import Neo4jClient

log = get_logger("reconciler")

_running = True

def _handle_stop(signum, _frame) -> None:
    """ Gestion des signaux SIGTERM et SIGINT pour un arrêt propre du reconciler."""
    global _running
    log.info("Signal %s reçu : arrêt après le cycle en cours.", signum)
    _running = False

def run_once(netbox: NetBoxClient, neo4j: Neo4jClient) -> None:
    """Exécute un cycle complet de synchronisation NetBox → Neo4j."""
    log.info("Début d'un cycle de synchronisation NetBox → Neo4j…")
    roles = mapping.build_role_hierarchy(netbox)
    neo4j.ensure_constraints(roles.all_names())

    # Récupération des périphériques, des interfaces, des adresses IP et des consoles depuis NetBox
    interfaces = list(netbox.iter_objects("/api/dcim/interfaces/"))
    iface_index = {i["id"]: i for i in interfaces}
    ips_by_dev = mapping.group_by(
        netbox.iter_objects("/api/ipam/ip-addresses/"), mapping._ip_device_id
    )
    consoles_by_dev = mapping.group_by(
        netbox.iter_objects("/api/dcim/console-ports/"), mapping._console_device_id
    )

    # 1) Nœuds device.
    seen_ids: set[int] = set()
    for device in netbox.iter_objects("/api/dcim/devices/"):
        did = device["id"]
        res = mapping.device_props(
            device, roles, ips_by_dev.get(did, []), consoles_by_dev.get(did, [])
        )
        if res:
            neo4j.upsert_device(*res)
            seen_ids.add(did)

    # 2) Relations EST_CONNECTE_A (une par câble).
    seen_cables: set[str] = set()
    for cable in netbox.iter_objects("/api/dcim/cables/"):
        rel = mapping.cable_rel(cable, iface_index)
        if rel:
            neo4j.upsert_connected(*rel)
            seen_cables.add(rel[2])

    # 3) Purge de ce qui a disparu de NetBox.
    neo4j.prune_devices(seen_ids, roles.all_names())
    neo4j.prune_connected(seen_cables)

    # 4) Rattachement de tous les devices au site (:SITE, référentiel interne).
    neo4j.ensure_site(settings.site_nom)
    linked = neo4j.link_devices_to_site(settings.site_nom)

    log.info(
        "Cycle terminé : %d device(s), %d relation(s) EST_CONNECTE_A, "
        "%d device(s) rattaché(s) au site %s (EST_HEBERGE_DANS).",
        len(seen_ids), len(seen_cables), linked, settings.site_nom,
    )


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    neo4j = Neo4jClient()
    netbox = NetBoxClient()

    log.info(
        "Reconciler démarré (NetBox=%s, Neo4j=%s, intervalle=%ds)",
        settings.netbox_api_url, settings.neo4j_uri, settings.reconcile_interval_seconds,
    )

    try:
        while _running:
            try:
                run_once(netbox, neo4j)
            except Exception:  # noqa: BLE001
                log.exception("Échec du cycle ; nouvelle tentative au prochain intervalle.")

            for _ in range(settings.reconcile_interval_seconds):
                if not _running:
                    break
                time.sleep(1)
    finally:
        netbox.close()
        neo4j.close()
        log.info("Reconciler arrêté proprement.")


if __name__ == "__main__":
    main()

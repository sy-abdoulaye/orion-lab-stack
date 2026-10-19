"""Client Neo4j : modèle dénormalisé (device étiqueté par rôle) + relation EST_CONNECTE_A.

Les labels sont dynamiques (= rôles NetBox). Un label ne peut pas être passé en
paramètre Cypher : il est back-quoté et validé (rejet de tout backtick) pour éviter
l'injection. Les valeurs (Id, propriétés) sont toujours passées en paramètres.
"""

from __future__ import annotations

from typing import Iterable

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from common.config import settings
from common.logging import get_logger

log = get_logger("neo4j")

_TRANSIENT = (ServiceUnavailable, SessionExpired)


def sanitize_label(role_name: str) -> str:
    """Valide un nom de rôle destiné à devenir un label Neo4j (back-quoté)."""
    if not role_name or "`" in role_name:
        raise ValueError(f"Nom de rôle invalide pour un label: {role_name!r}")
    return role_name


class Neo4jClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        """Ferme le driver Neo4j (connexion HTTP/bolt)."""
        self._driver.close()

    def verify_connectivity(self) -> None:
        """Vérifie la connectivité avec Neo4j (lève ServiceUnavailable si injoignable)."""
        self._driver.verify_connectivity()

    @retry(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _run(self, query: str, **params):
        """Exécute une requête Cypher avec retry sur erreurs transitoires (timeout, 5xx, session expirée).
            Retourne la liste des lignes (dict)."""
        with self._driver.session() as session:
            return list(session.run(query, **params))

    # ── Schéma ──────────────────────────────────────────────────────────
    def ensure_constraints(self, role_labels: Iterable[str]) -> None:
        """Crée les contraintes d'unicité sur Id pour chaque label de rôle."""
        n = 0
        for role in sorted(set(role_labels)):
            label = sanitize_label(role)
            # Nom de contrainte sûr (indépendant du back-quote du label).
            cname = "cid_" + "".join(c if c.isalnum() else "_" for c in role)
            self._run(
                f"CREATE CONSTRAINT {cname} IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.Id IS UNIQUE"
            )
            n += 1
        log.info("Contraintes d'unicité (Id) assurées sur %d rôle(s)", n)

    # ── Nœud device (label = rôle) ──────────────────────────────────────
    def upsert_device(self, role_label: str, device_id: int, props: dict) -> None:
        """Crée ou met à jour un nœud device (label = rôle) avec ses propriétés.
            Le label est back-quoté et validé pour éviter l'injection. Les propriétés sont passées en paramètre."""
        label = sanitize_label(role_label)
        # SET n = $props réinitialise entièrement les propriétés (reflète l'état
        # courant NetBox). props DOIT contenir "Id".
        self._run(
            f"MERGE (n:`{label}` {{Id: $device_id}}) SET n = $props",
            device_id=device_id,
            props=props,
        )

    def delete_device(self, device_id: int) -> None:
        """Supprime un nœud device par Id (quel que soit son label)."""
        # Sans label (le rôle peut avoir changé) : petit graphe, acceptable.
        self._run("MATCH (n {Id: $device_id}) DETACH DELETE n", device_id=device_id)

    def prune_devices(self, seen_ids: Iterable[int], known_labels: Iterable[str]) -> int:
        """Supprime les devices dont l'Id n'a pas été vu (parcours par label de rôle)."""
        deleted = 0
        for role in sorted(set(known_labels)):
            label = sanitize_label(role)
            rows = self._run(
                f"MATCH (n:`{label}`) WHERE NOT n.Id IN $ids "
                f"DETACH DELETE n RETURN count(n) AS c",
                ids=list(seen_ids),
            )
            deleted += rows[0]["c"] if rows else 0
        if deleted:
            log.info("Purge devices: %d nœud(s) obsolète(s) supprimé(s)", deleted)
        return deleted

    # ── Nœud :SITE + relation EST_HEBERGE_DANS ──────────────────────────
    # Le nœud :SITE (Nom = référentiel interne, ex. 782061) n'est PAS un
    # device NetBox : pas de propriété Id, pour qu'il échappe à delete_device
    # et prune_devices qui identifient les devices par Id.
    def ensure_site(self, nom: str) -> None:
        """Crée le nœud :SITE (Nom = référentiel interne) s'il n'existe pas, avec la propriété Role='SITE'."""
        self._run(
            "CREATE CONSTRAINT site_nom IF NOT EXISTS "
            "FOR (s:SITE) REQUIRE s.Nom IS UNIQUE"
        )
        self._run(
            "MERGE (s:SITE {Nom: $nom}) SET s.Role = 'SITE'",
            nom=nom,
        )

    def link_device_to_site(self, device_id: int, nom: str) -> None:
        """Rattache un device (Id) au site (Nom) via la relation EST_HEBERGE_DANS.
            Crée le nœud :SITE si nécessaire. Le device doit exister."""
        # Variante ciblée pour le receiver (webhook) : rattache immédiatement
        # un device créé/resynchronisé, sans attendre le prochain cycle du
        # reconciler. MERGE du site : un webhook peut précéder le premier cycle.
        self._run(
            "MERGE (s:SITE {Nom: $nom}) ON CREATE SET s.Role = 'SITE' "
            "WITH s MATCH (d) WHERE d.Id = $device_id AND NOT d:SITE "
            "MERGE (d)-[:EST_HEBERGE_DANS]->(s)",
            nom=nom,
            device_id=device_id,
        )

    def link_devices_to_site(self, nom: str) -> int:
        """Rattache tous les devices existants au site (Nom) via la relation EST_HEBERGE_DANS.
            Crée le nœud :SITE si nécessaire. Retourne le nombre de relations créées."""
        # Tous les devices NetBox portent un Id ; :SITE et les nœuds des autres
        # synchros (ex. :Prefix) n'en ont pas.
        rows = self._run(
            "MATCH (s:SITE {Nom: $nom}) "
            "MATCH (d) WHERE d.Id IS NOT NULL AND NOT d:SITE "
            "MERGE (d)-[:EST_HEBERGE_DANS]->(s) "
            "RETURN count(d) AS c",
            nom=nom,
        )
        return rows[0]["c"] if rows else 0

    # ── Relation EST_CONNECTE_A (device -> device, une par câble) ─────────
    def upsert_connected(self, a_id: int, b_id: int, cable_name: str, props: dict) -> None:
        """Crée ou met à jour une relation EST_CONNECTE_A entre deux devices (Id) avec ses propriétés.
            Le nom du câble est unique par relation. Les propriétés sont passées en paramètre."""
        self._run(
            "MATCH (a {Id: $a_id}) MATCH (b {Id: $b_id}) "
            "MERGE (a)-[r:EST_CONNECTE_A {CableName: $cable_name}]->(b) SET r = $props",
            a_id=a_id,
            b_id=b_id,
            cable_name=cable_name,
            props=props,
        )

    def delete_connected(self, cable_name: str) -> None:
        """Supprime la relation EST_CONNECTE_A par nom de câble (quel que soit le device)."""
        self._run(
            "MATCH ()-[r:EST_CONNECTE_A {CableName: $cable_name}]-() DELETE r",
            cable_name=cable_name,
        )

    def prune_connected(self, seen_cables: Iterable[str]) -> int:
        """Supprime les relations EST_CONNECTE_A dont le nom de câble n'a pas été vu."""
        rows = self._run(
            "MATCH ()-[r:EST_CONNECTE_A]->() WHERE NOT r.CableName IN $names "
            "DELETE r RETURN count(r) AS c",
            names=list(seen_cables),
        )
        deleted = rows[0]["c"] if rows else 0
        if deleted:
            log.info("Purge relations: %d EST_CONNECTE_A obsolète(s) supprimé(s)", deleted)
        return deleted

    # ── Administration ──────────────────────────────────────────────────
    def wipe_all(self, drop_constraints: bool = False) -> int:
        """Supprime tous les nœuds et relations. Optionnellement les contraintes."""
        rows = self._run("MATCH (n) DETACH DELETE n RETURN count(n) AS c")
        deleted = rows[0]["c"] if rows else 0
        if drop_constraints:
            for row in self._run("SHOW CONSTRAINTS YIELD name RETURN name"):
                self._run(f"DROP CONSTRAINT {row['name']} IF EXISTS")
        log.info("Wipe: %d nœud(s) supprimé(s)%s", deleted,
                 " + contraintes" if drop_constraints else "")
        return deleted

    def counts(self) -> dict:
        """Retourne un dict avec le nombre de nœuds, de relations EST_CONNECTE_A et la liste des labels."""
        labels = [r["label"] for r in self._run("CALL db.labels() YIELD label RETURN label ORDER BY label")]
        nodes = self._run("MATCH (n) RETURN count(n) AS c")[0]["c"]
        rels = self._run("MATCH ()-[r:EST_CONNECTE_A]->() RETURN count(r) AS c")[0]["c"]
        return {"labels": labels, "nodes": nodes, "connected": rels}

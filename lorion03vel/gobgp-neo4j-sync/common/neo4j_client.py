"""Client Neo4j : topologie BGP-LS greffée sur les équipements NetBox existants.

Le graphe est partagé avec netbox-neo4j-sync qui possède les nœuds équipement
(labels par rôle : peag, gp, rr..., propriété d'identité `Nom`). Ce client ne
crée JAMAIS de nœud équipement (pas de label Router) : chaque routeur BGP-LS
est retrouvé par match insensible à la casse sur `Nom`. Seuls les nœuds
:Prefix appartiennent à cette synchro.

netbox-neo4j-sync réécrit les propriétés des nœuds équipement (`SET n =`) à
chaque reconcile : les propriétés BGP posées sur ces nœuds (`SET n +=`) sont
donc volatiles, l'état durable vit sur les RELATIONS (ISIS,
ANNOUNCES_PREFIX, ANNOUNCES_ROUTE).

Deux modes d'écriture, utilisés respectivement par les deux boucles du reconciler :
- upsert_* (cycle topologie, tables d'état) : remplace l'état courant de la
  relation (props déjà consolidées depuis les sources ClickHouse).
- update_*_withdraw (cycle monitor, tables `monitor_bgp*`) : mise à jour CIBLÉE
  (`Withdraw`, `LastEventAge`) sur une relation déjà existante, sans jamais
  écraser les propriétés posées par le cycle topologie. Si la relation n'existe
  pas encore, la ligne est ignorée (elle sera créée au prochain cycle topologie).

Les noms d'équipement passés en paramètre doivent être PRÉ-NORMALISÉS en
minuscules (voir reconciler/main.py).
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


class Neo4jClient:
    """Client Neo4j pour la synchro BGP-LS : nœuds :Prefix + relations ISIS/ANNOUNCES_PREFIX/ANNOUNCES_ROUTE."""
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

    """ Exécute une requête Neo4j et renvoie les résultats. """
    @retry(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _run(self, query: str, **params):
        with self._driver.session() as session:
            return list(session.run(query, **params))

    # ── Schéma ──────────────────────────────────────────────────────────
    def ensure_constraints(self) -> None:
        """Crée les contraintes d'unicité sur Prefix.Key (et supprime l'ancien router_igp_router_id)."""
        # Héritage de l'ancien modèle à nœuds :Router, sans objet désormais.
        self._run("DROP CONSTRAINT router_igp_router_id IF EXISTS")
        self._run(
            "CREATE CONSTRAINT prefix_key IF NOT EXISTS "
            "FOR (p:Prefix) REQUIRE p.Key IS UNIQUE"
        )
        log.info("Contrainte d'unicité assurée (Prefix.Key).")

    # ── Nœuds équipement (propriété NetBox `Nom`, jamais créés ici) ────
    def update_equipment_bgp(self, name: str, props: dict) -> bool:
        """Met à jour les propriétés BGP d'un nœud équipement existant (Nom insensible à la casse)."""
        rows = self._run(
            "MATCH (n) WHERE toLower(n.Nom) = $name "
            "SET n += $props RETURN count(n) AS c",
            name=name,
            props=props,
        )
        return bool(rows and rows[0]["c"])

    def update_router_withdraw(self, name: str, withdraw: bool, last_event_age) -> bool:
        """Met à jour le retrait d'un nœud équipement existant (Nom insensible à la casse)."""
        return self.update_equipment_bgp(
            name, {"Withdraw": withdraw, "LastEventAge": last_event_age}
        )

    def upsert_prefix(self, key: str, props: dict) -> None:
        """Crée ou met à jour un nœud :Prefix avec ses propriétés (clé = family + prefix)."""
        self._run(
            "MERGE (p:Prefix {Key: $key}) SET p = $props",
            key=key,
            props={**props, "Key": key},
        )

    def prune_prefixes(self, seen_keys: Iterable[str]) -> int:
        """Supprime les nœuds :Prefix dont la clé n'est pas dans seen_keys (obsolètes)."""
        rows = self._run(
            "MATCH (p:Prefix) WHERE NOT p.Key IN $keys "
            "DETACH DELETE p RETURN count(p) AS c",
            keys=list(seen_keys),
        )
        deleted = rows[0]["c"] if rows else 0
        if deleted:
            log.info("Purge Prefix : %d nœud(s) obsolète(s) supprimé(s).", deleted)
        return deleted

    # ── Relation ISIS (équipement -> équipement, une par lien) ───
    # `SET r +=` (et non `SET r =`) : bgp_ls_links ne porte pas Withdraw, un
    # remplacement complet effacerait le Withdraw/LastEventAge posé par le
    # cycle monitor entre deux cycles topologie.
    def upsert_adjacent(self, local_name: str, remote_name: str, key: str, props: dict) -> bool:
        """Crée ou met à jour une relation ISIS entre deux équipements existants (Nom insensible à la casse)."""
        rows = self._run(
            "MATCH (a) WHERE toLower(a.Nom) = $local_name "
            "MATCH (b) WHERE toLower(b.Nom) = $remote_name "
            "MERGE (a)-[r:ISIS {Key: $key}]->(b) "
            "ON CREATE SET r = $props, r.Withdraw = false "
            "ON MATCH SET r += $props "
            "RETURN count(r) AS c",
            local_name=local_name,
            remote_name=remote_name,
            key=key,
            props={**props, "Key": key},
        )
        return bool(rows and rows[0]["c"])

    def update_adjacent_withdraw(self, key: str, withdraw: bool, last_event_age) -> bool:
        """Met à jour le retrait d'une relation ISIS existante (clé = family + local + remote)."""
        rows = self._run(
            "MATCH ()-[r:ISIS {Key: $key}]->() "
            "SET r.Withdraw = $withdraw, r.LastEventAge = $age "
            "RETURN count(r) AS c",
            key=key,
            withdraw=withdraw,
            age=last_event_age,
        )
        return bool(rows and rows[0]["c"])

    def prune_adjacent(self, seen_keys: Iterable[str]) -> int:
        """Supprime les relations ISIS dont la clé n'est pas dans seen_keys (obsolètes)."""
        rows = self._run(
            "MATCH ()-[r:ISIS]->() WHERE NOT r.Key IN $keys "
            "DELETE r RETURN count(r) AS c",
            keys=list(seen_keys),
        )
        deleted = rows[0]["c"] if rows else 0
        if deleted:
            log.info("Purge ISIS : %d relation(s) obsolète(s) supprimée(s).", deleted)
        return deleted

    # ── Relation ANNOUNCES_PREFIX (équipement -> Prefix, IGP) ───────────
    def upsert_announces_prefix(self, name: str, prefix_key: str, props: dict) -> bool:
        """Crée ou met à jour une relation ANNOUNCES_PREFIX entre un équipement existant et un nœud :Prefix existant."""
        rows = self._run(
            "MATCH (n) WHERE toLower(n.Nom) = $name "
            "MATCH (p:Prefix {Key: $pkey}) "
            "MERGE (n)-[rel:ANNOUNCES_PREFIX]->(p) SET rel = $props "
            "RETURN count(rel) AS c",
            name=name,
            pkey=prefix_key,
            props=props,
        )
        return bool(rows and rows[0]["c"])

    def update_announces_prefix_withdraw(self, name: str, prefix_key: str, withdraw: bool, last_event_age) -> bool:
        """Met à jour le retrait d'une relation ANNOUNCES_PREFIX existante (Nom insensible à la casse + clé)."""
        rows = self._run(
            "MATCH (n)-[rel:ANNOUNCES_PREFIX]->(:Prefix {Key: $pkey}) "
            "WHERE toLower(n.Nom) = $name "
            "SET rel.Withdraw = $withdraw, rel.LastEventAge = $age "
            "RETURN count(rel) AS c",
            name=name,
            pkey=prefix_key,
            withdraw=withdraw,
            age=last_event_age,
        )
        return bool(rows and rows[0]["c"])

    def prune_announces_prefix(self, seen_pairs: Iterable[tuple[str, str]]) -> int:
        """Supprime les relations ANNOUNCES_PREFIX dont le couple (Nom, Prefix.Key) n'est pas dans seen_pairs (obsolètes)."""
        rows = self._run(
            "MATCH (n)-[rel:ANNOUNCES_PREFIX]->(p:Prefix) "
            "WHERE NOT [toLower(n.Nom), p.Key] IN $pairs "
            "DELETE rel RETURN count(rel) AS c",
            pairs=[list(pair) for pair in seen_pairs],
        )
        deleted = rows[0]["c"] if rows else 0
        if deleted:
            log.info("Purge ANNOUNCES_PREFIX : %d relation(s) obsolète(s) supprimée(s).", deleted)
        return deleted

    # ── Relation ANNOUNCES_ROUTE (équipement -> Prefix, BGP classique) ──
    # L'équipement est résolu en amont via OriginatorId -> NodeName (voir
    # reconciler/main.py). Le nœud Prefix n'est créé que si le MATCH équipement
    # réussit (MERGE en aval du MATCH) : évite de semer des Prefix orphelins.
    def upsert_announces_route(self, name: str,
                               prefix_key: str, prefix_props: dict, family: str, props: dict) -> bool:
        """Crée ou met à jour une relation ANNOUNCES_ROUTE entre un équipement existant et un nœud :Prefix (créé si nécessaire)."""
        rows = self._run(
            "MATCH (n) WHERE toLower(n.Nom) = $name "
            "MERGE (p:Prefix {Key: $pkey}) ON CREATE SET p = $prefix_props "
            "MERGE (n)-[rel:ANNOUNCES_ROUTE {Family: $family}]->(p) SET rel = $props "
            "RETURN count(rel) AS c",
            name=name,
            pkey=prefix_key,
            prefix_props=prefix_props,
            family=family,
            props={**props, "Family": family},
        )
        return bool(rows and rows[0]["c"])

    # ── Administration ──────────────────────────────────────────────────
    # Propriétés posées par cette synchro sur les nœuds équipement NetBox
    # (update_equipment_bgp / update_router_withdraw) : retirées par wipe_all.
    _BGP_EQUIPMENT_PROPS = [
        "Name", "Asn", "Overload", "BgpLsId", "LastSeen", "RouterId",
        "IsisArea", "Protocol", "Withdraw", "IgpRouterId", "LastEventAge",
    ]

    # Ne supprime QUE les données de cette synchro (relations BGP, nœuds
    # :Prefix, propriétés BGP posées sur les équipements) : les nœuds
    # équipement eux-mêmes appartiennent à netbox-neo4j-sync.
    def wipe_all(self) -> int:
        self._run(
            "MATCH ()-[r:ISIS|ANNOUNCES_PREFIX|ANNOUNCES_ROUTE]->() DELETE r"
        )
        rows = self._run("MATCH (p:Prefix) DETACH DELETE p RETURN count(p) AS c")
        deleted = rows[0]["c"] if rows else 0
        # SET n += {prop: null} retire la propriété ; no-op si déjà absente.
        cleaned_rows = self._run(
            "MATCH (n) WHERE NOT n:Prefix AND any(k IN $keys WHERE n[k] IS NOT NULL) "
            "SET n += $nulls RETURN count(n) AS c",
            keys=self._BGP_EQUIPMENT_PROPS,
            nulls={k: None for k in self._BGP_EQUIPMENT_PROPS},
        )
        cleaned = cleaned_rows[0]["c"] if cleaned_rows else 0
        log.info(
            "Wipe : relations BGP supprimées, %d nœud(s) Prefix supprimé(s), "
            "propriétés BGP retirées de %d nœud(s) équipement.",
            deleted, cleaned,
        )
        return deleted

    def counts(self) -> dict:
        """Retourne le nombre de nœuds et de relations par type."""
        nodes = {
            row["label"]: row["c"]
            for row in self._run(
                "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS c"
            )
        }
        rels = {
            row["type"]: row["c"]
            for row in self._run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c"
            )
        }
        return {"nodes": nodes, "relationships": rels}

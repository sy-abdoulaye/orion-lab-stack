"""Configuration centralisée, lue depuis l'environnement (12-factor).

Un unique objet `settings` est importé par le reconciler et le CLI admin.
Les valeurs proviennent des variables d'environnement (injectées via `env_file`
dans compose) ; `python-dotenv` permet aussi un `.env` local en développement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Charge un éventuel .env local (no-op si absent) ; en production les variables
# viennent déjà de l'environnement du conteneur.
load_dotenv()


def _env_or_file(name: str, default: str = "") -> str:
    """Secret lu depuis le fichier pointé par <name>_FILE (montage `secrets:`
    du compose, prioritaire), sinon depuis la variable <name> elle-même.
    Permet de garder le .env versionnable (aucun secret dedans)."""
    path = os.environ.get(f"{name}_FILE")
    if path:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    """Paramètres de configuration, lus depuis l'environnement."""
    # ClickHouse (protocole natif, port 9000 : le HTTP casse avec le proxy
    # d'entreprise de cette infra, voir lorion01vel/gobgp/scripts/load_clickhouse.sh)
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_database: str

    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    # Reconciler
    reconcile_interval_seconds: int
    monitor_poll_interval_seconds: int
    monitor_window_seconds: int

    # Divers
    log_level: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            clickhouse_host=os.environ.get("CLICKHOUSE_HOST", "10.10.3.141"),
            clickhouse_port=int(os.environ.get("CLICKHOUSE_PORT", "9000")),
            clickhouse_user=os.environ.get("CLICKHOUSE_USER", "gobgp_reader"),
            clickhouse_password=_env_or_file("CLICKHOUSE_PASSWORD"),
            clickhouse_database=os.environ.get("CLICKHOUSE_DATABASE", "gobgp"),
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://lorion03vel-neo4j:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=_env_or_file("NEO4J_PASSWORD"),
            reconcile_interval_seconds=int(os.environ.get("RECONCILE_INTERVAL_SECONDS", "300")),
            monitor_poll_interval_seconds=int(os.environ.get("MONITOR_POLL_INTERVAL_SECONDS", "20")),
            monitor_window_seconds=int(os.environ.get("MONITOR_WINDOW_SECONDS", "120")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )


settings = Settings.from_env()

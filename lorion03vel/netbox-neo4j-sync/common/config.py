"""Configuration centralisée, lue depuis l'environnement (12-factor).

Un unique objet `settings` est importé par le receiver et le reconciler.
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


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    # NetBox
    netbox_api_url: str
    netbox_token: str
    netbox_verify_ssl: bool

    # Webhook
    webhook_secret: str

    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    # Reconciler
    reconcile_interval_seconds: int
    # Nom du nœud :SITE (référentiel interne, pas le nom du site NetBox)
    # auquel tous les devices sont rattachés par EST_HEBERGE_DANS.
    site_nom: str

    # Divers
    log_level: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            netbox_api_url=os.environ.get("NETBOX_API_URL", "http://netbox:8080").rstrip("/"),
            netbox_token=_env_or_file("NETBOX_TOKEN"),
            netbox_verify_ssl=_bool(os.environ.get("NETBOX_VERIFY_SSL"), default=False),
            webhook_secret=_env_or_file("WEBHOOK_SECRET"),
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://lorion03vel-neo4j:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=_env_or_file("NEO4J_PASSWORD"),
            reconcile_interval_seconds=int(os.environ.get("RECONCILE_INTERVAL_SECONDS", "900")),
            site_nom=os.environ.get("SITE_NOM", "782061"),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )


settings = Settings.from_env()

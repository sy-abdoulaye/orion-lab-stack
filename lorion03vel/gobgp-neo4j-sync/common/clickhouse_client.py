"""Client ClickHouse en lecture seule (base gobgp).

Protocole natif (port 9000) via `clickhouse-driver` : le HTTP (8123/curl) casse
avec le proxy d'entreprise de cette infra (voir
lorion01vel/gobgp/scripts/load_clickhouse.sh), donc pas de clickhouse-connect ici.
"""

from __future__ import annotations

from clickhouse_driver import Client
from clickhouse_driver.errors import Error as ClickHouseError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from common.config import settings
from common.logging import get_logger

log = get_logger("clickhouse")

_TRANSIENT = (ClickHouseError, ConnectionError, TimeoutError, OSError)


class ClickHouseReader:
    """Client ClickHouse en lecture seule (base gobgp)."""
    def __init__(self) -> None:
        self._client = Client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            user=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            connect_timeout=10,
            send_receive_timeout=60,
        )

    def close(self) -> None:
        self._client.disconnect()

    @retry(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def query_dicts(self, sql: str, params: dict | None = None) -> list[dict]:
        """Exécute une requête et renvoie chaque ligne comme un dict {colonne: valeur}.

        Exécution eager (pas un générateur) : la requête ClickHouse doit se
        terminer *à l'intérieur* du bloc retry pour que les erreurs transitoires
        déclenchent bien une nouvelle tentative.
        """
        rows, columns = self._client.execute(sql, params or {}, with_column_types=True)
        names = [c[0] for c in columns]
        return [dict(zip(names, row)) for row in rows]

"""Client HTTP pour l'API REST NetBox (lecture seule, avec pagination)."""

from __future__ import annotations

from typing import Iterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from common.config import settings
from common.logging import get_logger

log = get_logger("netbox")

_TRANSIENT = (httpx.TransportError, httpx.HTTPStatusError)


class NetBoxClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.netbox_api_url,
            headers={
                "Authorization": f"Token {settings.netbox_token}",
                "Accept": "application/json",
            },
            verify=settings.netbox_verify_ssl,
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    @retry(
        retry=retry_if_exception_type(_TRANSIENT),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> dict:
        """GET avec retry sur erreurs transitoires (timeout, 5xx)."""
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_object(self, path: str) -> dict:
        """Récupère un objet unique, ex. `/api/dcim/devices/122/`."""
        if not settings.netbox_token:
            raise RuntimeError("NETBOX_TOKEN est vide : renseignez un token API NetBox dans .env.")
        return self._get(path)

    # ── Écriture (utilisé par le CLI d'administration) ──────────────────
    def list_objects(self, path: str, **filters) -> list[dict]:
        """Liste (1re page) filtrée, ex. list_objects('/api/extras/webhooks/', name='x')."""
        return self._get(path, params=filters).get("results", [])

    def create(self, path: str, payload: dict) -> dict:
        """Crée un nouvel objet, ex. create('/api/extras/webhooks/', {...})."""
        resp = self._client.post(path, json=payload)
        resp.raise_for_status()
        return resp.json()

    def patch(self, path: str, payload: dict) -> dict:
        """Met à jour un objet existant, ex. patch('/api/extras/webhooks/12/', {...})."""
        resp = self._client.patch(path, json=payload)
        resp.raise_for_status()
        return resp.json()

    def remove(self, path: str) -> None:
        """Supprime un objet existant, ex. remove('/api/extras/webhooks/12/')."""
        resp = self._client.delete(path)
        resp.raise_for_status()

    def iter_objects(self, endpoint: str, page_size: int = 200) -> Iterator[dict]:
        """Itère sur tous les objets d'un endpoint DCIM en suivant `next`.

        `endpoint` ex.: "/api/dcim/devices/".
        """
        if not settings.netbox_token:
            raise RuntimeError(
                "NETBOX_TOKEN est vide : renseignez un token API NetBox dans .env "
                "(Admin -> API Tokens) puis redémarrez le service."
            )
        url: str | None = endpoint
        # NB: ne PAS envoyer `brief` — NetBox active le mode abrégé dès que le
        # paramètre est présent (même `brief=false`), ce qui retire les objets
        # liés imbriqués (site, role, device_type, terminations de câble...).
        params: dict | None = {"limit": page_size}
        count_total = None
        yielded = 0
        while url:
            data = self._get(url, params=params)
            if count_total is None:
                count_total = data.get("count")
            for obj in data.get("results", []):
                yielded += 1
                yield obj
            # `next` est une URL absolue ; httpx la gère telle quelle. On ne
            # repasse pas `params` car ils sont déjà encodés dans `next`.
            url = data.get("next")
            params = None
        log.info("NetBox %s: %d objet(s) récupéré(s) (total annoncé=%s)",
                 endpoint, yielded, count_total)

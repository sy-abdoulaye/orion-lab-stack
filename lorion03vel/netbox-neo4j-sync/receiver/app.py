"""Receiver FastAPI : reçoit les webhooks NetBox et applique dans Neo4j.

NetBox signe le corps du webhook avec HMAC-SHA512 (clé = secret du webhook)
et envoie le digest hex dans l'en-tête `X-Hook-Signature`. On vérifie cette
signature avant tout traitement.

Modèle dénormalisé : sur webhook d'un sous-objet (interface, ip, console, câble),
on resynchronise le/les device(s) concerné(s) en ré-interrogeant l'API NetBox.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response

from common import mapping
from common.config import settings
from common.logging import get_logger
from common.netbox_client import NetBoxClient
from common.neo4j_client import Neo4jClient

log = get_logger("receiver")

_UPSERT_EVENTS = {"created", "updated"}
_DELETE_EVENTS = {"deleted"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Contexte de vie de l'application FastAPI : on crée les clients Neo4j et NetBox,
    on construit la hiérarchie des rôles, et on ferme les clients à la fin"""
    app.state.neo4j = Neo4jClient()
    app.state.netbox = NetBoxClient()
    app.state.roles = mapping.build_role_hierarchy(app.state.netbox)
    log.info("Receiver démarré (Neo4j=%s, NetBox=%s)", settings.neo4j_uri, settings.netbox_api_url)
    try:
        yield
    finally:
        app.state.neo4j.close()
        app.state.netbox.close()

""" FastAPI application instance avec lifespan context manager."""
app = FastAPI(title="netbox-neo4j-sync receiver", lifespan=lifespan)

def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    """ Vérifie la signature HMAC-SHA512 du corps du webhook. Si le secret n'est pas défini, on log un warning et on ne vérifie pas la signature.
    Si la signature est manquante ou invalide, on lève une exception HTTP 401. """
    if not settings.webhook_secret:
        log.warning("WEBHOOK_SECRET non défini : vérification de signature désactivée")
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Signature manquante")
    expected = hmac.new(settings.webhook_secret.encode(), raw_body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Signature invalide")


@app.get("/healthz")
def healthz(request: Request) -> dict:
    """ Vérifie la connectivité avec Neo4j. Si Neo4j est injoignable, on lève une exception HTTP 503."""
    try:
        request.app.state.neo4j.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Neo4j injoignable: {exc}")
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_hook_signature: str | None = Header(default=None),
) -> Response:
    """ Point d'entrée du webhook NetBox. On vérifie la signature, on parse le JSON,
    et on applique la modification dans Neo4j."""
    raw = await request.body()
    _verify_signature(raw, x_hook_signature)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Corps JSON invalide")

    event = payload.get("event")
    # NetBox 4.x envoie `object_type` = "dcim.device" (pas `model`). On accepte
    # aussi `model` pour compat/tests. Le nom de modèle = partie après le point.
    object_type = payload.get("object_type") or ""
    model = payload.get("model") or (object_type.rsplit(".", 1)[-1] if object_type else None)
    data = payload.get("data") or {}
    if not model or "id" not in data:
        raise HTTPException(status_code=400, detail="Payload webhook incomplet")

    # On ne traite que les modèles connus (device, interface, ip, console, cable, devicerole).
    if model not in {"device", "interface", "ip", "console", "cable", "devicerole"}:
        log.debug("Modèle hors périmètre ignoré: %s", model)
        return Response(status_code=204)

    app_state = request.app.state
    # Un changement de rôle (hiérarchie) invalide le cache Fonction.
    if model == "devicerole":
        app_state.roles = mapping.build_role_hierarchy(app_state.netbox)

    if event in _UPSERT_EVENTS:
        handled = mapping.apply_webhook(app_state.netbox, app_state.neo4j, app_state.roles, model, data)
    elif event in _DELETE_EVENTS:
        handled = mapping.delete_webhook(app_state.netbox, app_state.neo4j, app_state.roles, model, data)
    else:
        raise HTTPException(status_code=400, detail=f"Événement inconnu: {event!r}")

    if not handled:
        log.debug("Modèle hors périmètre ignoré: %s", model)
        return Response(status_code=204)

    log.info("Webhook appliqué: event=%s model=%s id=%s", event, model, data.get("id"))
    return Response(status_code=200)

# netbox-neo4j-sync — Dépannage

Problèmes réellement rencontrés, avec résolution.

## Webhook → receiver renvoie **400 « Payload webhook incomplet »**

**Cause** : NetBox 4.5 envoie `object_type` (ex. `dcim.device`) et **pas** `model`. Un receiver
qui n'attend que `model` échoue.

**Solution** : le receiver déduit le modèle depuis `object_type`
(`object_type.rsplit(".", 1)[-1]`). Vérifier la version du code.

## Relations manquantes après un cycle (que `HAS_INTERFACE`/`MANUFACTURED_BY`)

**Cause** (modèle historique) : le paramètre `brief` envoyé à l'API NetBox. NetBox active le
mode abrégé dès que `brief` est **présent** (même `brief=false`), supprimant les objets liés
imbriqués (site, rôle, terminaisons).

**Solution** : ne **pas** envoyer `brief`. Le client NetBox a été corrigé en ce sens.

## `RuntimeError: NETBOX_TOKEN est vide`

**Cause** : `NETBOX_TOKEN` non renseigné dans `.env`.

**Solution** : créer un token (Admin → API Tokens), le placer dans `.env`, redémarrer le service.

## `httpx.LocalProtocolError: Illegal header value b'Token '`

**Cause** : token vide → en-tête `Authorization: Token ` invalide.

**Solution** : renseigner `NETBOX_TOKEN` (le client lève désormais une erreur claire avant l'appel).

## Webhook **401** (signature invalide)

**Cause** : `WEBHOOK_SECRET` du `.env` ≠ secret du Webhook NetBox.

**Solution** : aligner les deux (relancer `admin setup-webhooks` propage la valeur du `.env`).

## reconciler : `ValueError: Cannot resolve address lorion03vel-neo4j:7687`

**Cause** : Neo4j non démarré, ou service non attaché à `lorion03vel-network`.

**Solution** : démarrer Neo4j ; vérifier l'attachement réseau
(`docker inspect … NetworkSettings.Networks`).

## Doublons de webhooks / ancien endpoint

**Cause** : un ancien Webhook/Event Rule (créé manuellement) pointe vers un autre endpoint.

**Solution** : `admin teardown-webhooks --name <ancien>` ou nettoyage côté UI NetBox. Utiliser
`admin setup-webhooks` (idempotent) pour la config officielle.

## Port hôte 8000 déjà utilisé

**Cause** (si publication activée) : un autre service occupe 8000.

**Solution** : le receiver **n'est pas publié** sur l'hôte par défaut (NetBox l'appelle en
interne). Ne pas ajouter de mapping `8000:8000` sauf besoin de debug (utiliser alors `18000:8000`).

## Bonnes pratiques

!!! tip
    - Laisser le **reconciler** tourner : il rattrape les webhooks manqués.
    - Après toute modification de mapping, rebuild + `admin init`.
    - Vérifier régulièrement `admin stats` vs volumétrie NetBox.

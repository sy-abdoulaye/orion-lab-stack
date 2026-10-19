# NetBox — Dépannage (côté intégration)

Problèmes liés à l'**intégration** NetBox ↔ plateforme.

## `netbox:8080` injoignable depuis l'hôte

**Cause** : `netbox` est un nom DNS **interne** au réseau Docker.

**Solution** : depuis l'hôte, utiliser `http://localhost:9998`. Depuis un conteneur du réseau
`lorion03vel-network`, utiliser `http://netbox:8080`. Voir
[Réseau](../../architecture/networking.md).

## Webhook non reçu par le receiver

**Diagnostic ordonné** :

1. **Worker** actif ? C'est lui qui émet les webhooks :
   ```bash
   docker logs --since 2m netbox-docker-netbox-worker-1 | grep -i webhook
   ```
2. **Event Rule** existe et cible les bons objets ? (`admin setup-webhooks` la (re)crée).
3. **Réseau** : le worker doit joindre `netbox-neo4j-sync-receiver:8000` (même réseau
   `lorion03vel-network`).

## `Status 400 returned … webhook FAILED to process`

**Cause** : le receiver a répondu 400 (payload) ou 401 (signature).

**Solution** :
- 400 « Payload webhook incomplet » → format `object_type` (voir
  [sync / Dépannage](../netbox-neo4j-sync/troubleshooting.md)).
- 401 → `WEBHOOK_SECRET` désaligné entre NetBox et le sync.

## Doublons de webhooks

**Cause** : plusieurs Event Rules (ex. une ancienne manuelle + celle du CLI) ciblent les mêmes
objets.

**Solution** : conserver une seule configuration (`admin setup-webhooks`), supprimer les autres
(`admin teardown-webhooks --name <ancien>` ou via l'UI NetBox).

## Le worker n'émet rien mais NetBox fonctionne

**Cause** : worker arrêté, ou file Redis inaccessible.

**Solution** : vérifier `netbox-worker` (healthcheck `rqworker`), et `redis` (files RQ). Le
**reconciler** rattrapera les changements au cycle suivant.

## API 403 / token invalide

**Cause** : `NETBOX_TOKEN` expiré/insuffisant.

**Solution** : régénérer un token (Admin → API Tokens) avec les droits lecture DCIM + IPAM, le
placer dans le `.env` du sync.

## Bonnes pratiques

!!! tip
    - Toujours diagnostiquer un problème de webhook **du producteur vers le consommateur** :
      worker NetBox → réseau → receiver.
    - Garder le **reconciler** actif comme filet de sécurité.

# Exploitation — Vue d'ensemble

Cette section regroupe les procédures d'exploitation de la plateforme.

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Déploiement complet](deployment.md)**

    ---

    Ordre de démarrage, réseaux, bring-up de bout en bout.

-   :material-backup-restore: **[Sauvegarde & restauration](backup-restore.md)**

    ---

    Volumes Neo4j, ClickHouse, NetBox/PostgreSQL.

-   :material-update: **[Mises à jour & rollback](updates.md)**

    ---

    Montée de version des images, plugins, retour arrière.

-   :material-clipboard-check: **[Runbook](runbook.md)**

    ---

    Checklist d'exploitation et gestes courants.

</div>

## Périmètre géré ici

| Projet Compose | VM | Emplacement | Piloté par |
|----------------|----|-------------|------------|
| `lorion03vel` | lorion03vel | `orion-lab-stack/lorion03vel` | `make up/down/ps` (Neo4j, ClickHouse, syncs, docs) |
| `lorion01vel` | lorion01vel | `orion-lab-stack/lorion01vel` | `make up/down/ps` (gobgp, vector) |
| `lorion02vel` | lorion02vel | `orion-lab-stack/lorion02vel` | `make up/down/ps` (netbox-docker : NetBox & deps) |
| `netbox-docker` | lorion03vel | `/home/services/netbox-docker` | `docker compose` (NetBox & deps, hors dépôt) |

!!! info "Multi-VM, un point d'entrée"
    Les stacks des VM se pilotent depuis la **racine du dépôt** (`make deploy VM=…`,
    `make down VM=…`, `make status` — voir [Déploiement complet](deployment.md)). Le
    projet `netbox-docker` reste piloté séparément sur sa VM. Les procédures ci-dessous
    précisent à chaque fois le projet concerné.

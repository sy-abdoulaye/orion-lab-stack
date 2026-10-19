# Mise à jour de NetBox

## Prérequis

- Accès SSH au serveur `lviptauto01vel`
- Se placer dans le répertoire du projet :
  ```bash
  cd /home/services/netbox-docker
  ```

## 1. Vérifier la version actuelle

```bash
# Version de l'image en cours
docker inspect netbox-docker-netbox-1 --format '{{.Config.Image}}'

# Version configurée dans docker-compose.yml
grep 'VERSION' docker-compose.yml
```

La version est définie dans `docker-compose.yml` via la variable `${VERSION-v4.4-3.4.1}` (valeur par défaut si `VERSION` n'est pas définie).

## 2. Mettre à jour le repo upstream (docker-compose)

```bash
# Récupérer les dernières modifications du repo community
git fetch upstream

# Voir les changements disponibles
git log HEAD..upstream/release --oneline

# Merger les modifications
git merge upstream/release
```

En cas de conflit, résoudre manuellement puis :
```bash
git add <fichiers_résolus>
git commit
```

## 3. Mettre à jour la version NetBox

Deux méthodes possibles :

### Option A : Utiliser la version par défaut du repo upstream

Si le merge upstream a mis à jour la version par défaut dans `docker-compose.yml`, il suffit de ne pas définir la variable `VERSION`. La valeur par défaut du `docker-compose.yml` sera utilisée.

### Option B : Forcer une version spécifique

Créer ou modifier le fichier `.env` à la racine du projet :
```bash
echo "VERSION=v4.4-3.4.2" > .env
```

Les tags disponibles sont listés sur : https://hub.docker.com/r/netboxcommunity/netbox/tags

## 4. Sauvegarder la base de données

**Avant toute mise à jour, toujours sauvegarder PostgreSQL :**

```bash
docker-compose exec postgres pg_dump -U netbox netbox | gzip > netbox-backup-$(date +%Y%m%d-%H%M%S).sql.gz
```

Vérifier que le backup n'est pas vide :
```bash
ls -lh netbox-backup-*.sql.gz | tail -1
```

## 5. Appliquer la mise à jour

```bash
# Puller les nouvelles images
docker-compose pull

# Redémarrer avec les nouvelles images
docker-compose up -d
```

NetBox applique automatiquement les migrations de base de données au démarrage.

## 6. Vérifier la mise à jour

```bash
# Vérifier que tous les containers sont healthy
docker-compose ps

# Vérifier les logs de démarrage (migrations, erreurs)
docker-compose logs --tail=50 netbox

# Tester l'accès web
curl -f http://localhost:9999/login/ && echo "OK"
```

## 7. Commiter les changements

```bash
git add .
git commit -m "chore: upgrade netbox to <nouvelle_version>"
git push origin develop
```

## Rollback en cas de problème

### Restaurer la version précédente

```bash
# Spécifier l'ancienne version
echo "VERSION=v4.4-3.4.1" > .env

# Redémarrer
docker-compose up -d
```

### Restaurer la base de données

```bash
# Arrêter netbox
docker-compose stop netbox netbox-worker

# Restaurer le backup
gunzip -c netbox-backup-XXXXXXXX-XXXXXX.sql.gz | docker-compose exec -T postgres psql -U netbox netbox

# Redémarrer
docker-compose up -d
```

## Résumé rapide (cas nominal)

```bash
cd /home/services/netbox-docker

# Backup
docker-compose exec postgres pg_dump -U netbox netbox | gzip > netbox-backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Mise à jour upstream
git fetch upstream && git merge upstream/release

# Appliquer
docker-compose pull && docker-compose up -d

# Vérifier
docker-compose ps

# Commiter
git add . && git commit -m "chore: upgrade netbox to <version>" && git push origin develop
```

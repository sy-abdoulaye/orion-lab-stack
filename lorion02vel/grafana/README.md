# grafana — lorion02vel

Visualisation des données de la plateforme. Première stack de la VM lorion02vel,
suivant le pattern commun : réseau partagé `lorion02vel-network` (external, géré
par `make`), image via le **miroir interne**, plugin installé **au build** via le
proxy (pas d'internet à l'exécution), secrets en fichiers hors git.

## Démarrage

> **Particularité lorion02vel — CA du miroir non installée.** Le miroir
> `registry.example.com` est joignable, mais son certificat est signé par la
> CA interne, absente de la VM : tout pull direct échoue en
> `x509: certificate signed by unknown authority`. Deux options :
>
> ```bash
> # Option A (durable, sudo) : installer la CA (déposée dans ~/internal-root.crt,
> # copiée depuis /usr/local/share/ca-certificates/ de lorion03vel) :
> sudo cp ~/internal-root.crt /usr/local/share/ca-certificates/ \
>   && sudo update-ca-certificates && sudo systemctl restart docker
>
> # Option B (sans sudo) : transférer l'image de base depuis lorion03vel
> # (une fois par version de Grafana) :
> docker save registry.example.com/dockerhub/grafana/grafana:12.1.1 | gzip | \
>   ssh asy@10.10.2.11 'gunzip | docker load'
> ```
>
> Le build local (plugin ClickHouse) fonctionne dans les deux cas : la base
> est trouvée localement et grafana.com passe par le proxy (vérifié).
> Explication complète du problème : voir [Dépannage](#dépannage) en bas de page.

Prérequis VM (une fois, sudo) : `docker.io` + `docker-compose-v2` installés,
et `sudo usermod -aG docker asy` (puis se reconnecter).

```bash
# Secrets (une fois, sur la machine qui déploie) :
mkdir -p secrets && chmod 700 secrets
printf '%s' "$(openssl rand -base64 24 | tr -d '/+=')" > secrets/grafana_admin_password
printf '%s' "$(openssl rand -base64 32 | tr -d '/+=')" > secrets/grafana_secret_key
# clickhouse_grafana_password : même valeur que l'utilisateur `grafana`
# créé côté ClickHouse (lorion03vel) — voir « Datasource » ci-dessous.
# Fichiers 644 DANS un dossier 700 : Grafana tourne en uid 472 dans le
# conteneur et doit pouvoir lire les fichiers montés ; côté hôte, le dossier
# 700 bloque tout autre utilisateur. (600 -> « Permission denied » au démarrage.)
chmod 644 secrets/*

# Depuis le poste d'admin (pousse aussi .env + secrets/ au premier déploiement) :
make deploy VM=lorion02vel SECRETS=1
```

Accès : `http://10.10.2.11:3000/` — compte `admin`, mot de passe dans
`secrets/grafana_admin_password`.

## Gestion des utilisateurs

- **Auto-inscription désactivée** (`GF_USERS_ALLOW_SIGN_UP=false`) : seuls les
  comptes créés par l'admin existent.
- **Rôle par défaut : Viewer** (lecture seule) — promotion explicite en
  Editor/Admin, jamais l'inverse par défaut.
- **Anonyme désactivé**, création d'org désactivée.

Le cycle de vie des comptes passe par [`manage-users.sh`](manage-users.sh)
(API locale, authentifiée par le secret admin) :

```bash
./manage-users.sh list
./manage-users.sh create asy admin@example.com   # naît Viewer, mdp généré
./manage-users.sh set-role asy Editor
./manage-users.sh reset-password asy
./manage-users.sh delete asy
```

## Configuration

Déclarative, en trois couches — rien ne se configure dans l'UI :

| Couche | Fichier | Contenu |
|--------|---------|---------|
| Variables `GF_*` | [`compose.yml`](compose.yml) + [`.env`](.env) | serveur, sécurité, users |
| Datasources | [`provisioning/datasources/`](provisioning/datasources/) | ClickHouse lorion03vel (`editable: false`) |
| Dashboards | [`dashboards/`](dashboards/) (JSON versionnés) | chargés par le provider, lecture seule dans l'UI |

## Sécurité

- **Secrets en fichiers** (`./secrets/`, hors git, fichiers 644 dans un
  dossier 700 — cf. Démarrage) montés via `secrets:` ; convention Grafana
  `GF_*__FILE` pour l'admin et la clé de signature — aucun secret dans
  `.env` ni dans l'image.
- **Datasource ClickHouse en lecture seule** : utilisateur dédié `grafana`
  (rôle `SELECT` uniquement sur `gobgp.*`), créé côté lorion03vel via
  `clickhouse/manage-users.sh`. Grafana ne peut rien écrire ni lire ailleurs.
- **Aucun appel sortant** à l'exécution : analytics, check d'updates, news et
  snapshots externes désactivés (le lab est isolé de toute façon).
- `secret_key` dédiée (chiffrement des secrets internes de Grafana) — ne pas
  la changer après coup sans re-saisir les credentials des datasources.
- HTTP interne au lab : `GF_SECURITY_COOKIE_SECURE=false` ; passer à `true`
  si un jour Grafana est servi derrière TLS.

## Datasource ClickHouse (inter-VM)

Grafana (lorion02vel) joint ClickHouse (lorion03vel) par l'**IP hôte + port
natif publié** `10.10.3.141:9000` — c'est la voie normale inter-VM (le blocage
hairpin ne concerne que les conteneurs de lorion03vel eux-mêmes). L'utilisateur
`grafana` est créé côté ClickHouse avec le même mot de passe que
`secrets/clickhouse_grafana_password`.

## Dépannage

### `x509: certificate signed by unknown authority` au build/pull

**Symptôme** (rencontré au premier `make deploy VM=lorion02vel`, 2026-07-16) :

```text
#3 [internal] load metadata for registry.example.com/dockerhub/grafana/grafana:12.1.1
#3 ERROR: failed to do request: Head "https://registry.example.com/v2/...":
   tls: failed to verify certificate: x509: certificate signed by unknown authority
```

**Ce qui se passe.** Le miroir présente un certificat TLS signé par la
**CA interne** (`issuer: ACME Internal CA`), pas par une autorité publique :

```text
subject : CN = registry.example.com, OU = INFRA_TEAM
issuer  : CN = ACME Internal CA, O = ACME CORP
```

Une machine ne fait confiance qu'aux CA présentes dans son magasin système
(`/etc/ssl/certs`). Une VM fraîchement installée ne connaît que les CA
publiques : quand Docker contacte le miroir en HTTPS, la vérification de la
chaîne échoue → `unknown authority`. Ce n'est **ni un problème de réseau ni
de proxy** : la connexion TLS s'établit (le test `curl -k`, qui désactive la
vérification, répond 401 — la réponse normale du registre), c'est bien la
**confiance** qui manque.

**Pourquoi lorion03vel n'a pas ce problème.** La CA y a été installée :
`/usr/local/share/ca-certificates/internal-root.crt`, intégrée au magasin système
par `update-ca-certificates`. C'est ce fichier qu'il faut répliquer sur toute
nouvelle VM du lab (Option A du Démarrage).

**Pourquoi l'erreur survient au `build` alors qu'on ne « pull » pas.** Le
`FROM registry.example.com/...` du Dockerfile oblige buildkit à résoudre les
métadonnées de l'image de base ; si elle est **absente du cache local**, il
interroge le registre → TLS → échec. Dès que l'image est présente localement
(Option B : `docker save | ssh | docker load` depuis lorion03vel), buildkit
l'utilise sans contacter le registre, et le build passe.

**Diagnostic rapide** sur une VM :

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://registry.example.com/v2/     # échec TLS = CA absente
curl -sk -o /dev/null -w '%{http_code}\n' https://registry.example.com/v2/    # 401 = réseau OK, donc CA seule en cause
openssl s_client -connect registry.example.com:443 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer                                        # voir qui a signé
```

**Note** : ce choix (Option A vs B) ne concerne que le **pull de l'image de
base**. Le téléchargement du plugin ClickHouse au build passe, lui, par le
proxy d'entreprise (`BUILD_HTTP_PROXY`) vers grafana.com et fonctionne dans
les deux cas.

### `http://10.10.2.11:3000/` inaccessible depuis le poste de travail

**Symptôme** (constaté le 2026-07-16) : le navigateur n'ouvre pas Grafana,
et même en contournant le proxy, la connexion échoue en **timeout** :

```text
C:\> curl.exe -v --noproxy "*" http://10.10.2.11:3000/api/health
*   Trying 10.10.2.11:3000...
* connect to 10.10.2.11 port 3000 ... failed: Timed out
curl: (28) Failed to connect to server
```

**Ce qui se passe.** Grafana est **sain** — le distinguer d'une panne serveur
est tout l'enjeu du diagnostic :

| Test | Résultat | Conclusion |
|------|----------|------------|
| `docker ps` sur la VM | `Up (healthy)`, `0.0.0.0:3000->3000` | conteneur OK, port publié |
| `curl localhost:3000/api/health` sur la VM | 200 | Grafana répond |
| `curl 10.10.2.11:3000` **depuis une autre VM du lab** | 200 | pas de pare-feu VM |
| `ping 10.10.2.11` **depuis le poste** | réponse, TTL=56 | **la route existe** (ICMP passe) |
| `curl.exe --noproxy "*"` **depuis le poste** | timeout | **TCP 3000 filtré en chemin** |

La combinaison est parlante : le **ping répond** (ICMP, quasi toujours
autorisé par les pare-feux) mais la connexion **TCP 3000 tombe en timeout** —
et un timeout, contrairement à un « connection refused » immédiat, signifie
que les paquets SYN sont **jetés silencieusement (DROP)** par un pare-feu
entre le poste et le lab. Ce n'est ni Grafana, ni Docker, ni le proxy, ni le
routage : c'est du **filtrage par IP:port**.

> Rappel utile : `ping` teste ICMP, pas TCP — « ça ping » ne veut pas dire
> « le service est accessible », et inversement.

**Cause précise (confirmée)** : la règle d'ouverture **dépend du réseau
source**. Les postes du **réseau filaire** accèdent à `10.10.2.11:3000` ;
depuis le **WiFi**, seul l'ICMP passe, le TCP 3000 est filtré. Même
destination, deux politiques — selon le sous-réseau d'origine.

**« Faut-il ajouter des routes sur le poste ? »** Seulement si le poste a
**plusieurs accès réseau**. Une route ne crée pas de chemin : elle choisit
entre des chemins existants. C'est le cas de lviptauto01vel (4 interfaces →
ses routes statiques désignent la bonne patte par destination), pas celui
d'un poste WiFi mono-interface — le ping prouve d'ailleurs que ses paquets
arrivent déjà. En revanche, **si le poste est branché en filaire en plus du
WiFi** (dock), on peut forcer le trafic lab par la patte filaire :

```bat
ipconfig                    :: repérer la passerelle de l'interface FILAIRE
route -p add 10.10.2.0 mask 255.255.255.0 <passerelle-filaire>
```

(Windows privilégie en général le filaire quand il est branché — tester
d'abord sans route.) En WiFi seul : extension de la règle pare-feu au
sous-réseau WiFi, ou tunnel SSH ci-dessous.

**Contournement immédiat : tunnel SSH** via une machine joignable des deux
côtés (lviptauto01vel voit `10.10.2.11`) :

```bash
ssh -L 3000:10.10.2.11:3000 asy@lviptauto01vel
# puis dans le navigateur du poste : http://localhost:3000/
```

**Pistes durables** (au choix, selon la politique réseau du lab) :

1. Demander l'ouverture pare-feu **LAN bureautique → 10.10.2.11 : TCP 3000**
   (la voie propre — même traitement que la règle existante vers
   `10.10.3.141:9998` pour NetBox).
2. Publier Grafana derrière une IP déjà joignable : reverse proxy sur
   lorion03vel (ex. le nginx de la doc, `10.10.3.141`) qui proxifie vers
   `10.10.2.11:3000` — nécessite d'ajuster `GRAFANA_ROOT_URL` dans
   [`.env`](.env) pour que les redirections/liens de Grafana restent corrects.

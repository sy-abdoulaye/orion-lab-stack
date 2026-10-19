#!/usr/bin/env bash
# ============================================================
# deploy.sh — déploie une (ou toutes les) stack(s) VM depuis
# le poste d'administration, en un seul geste.
#
# Usage :
#   deploy/deploy.sh <vm-dir|all> [cible-make] [--with-secrets]
#
#   <vm-dir>        lorion01vel | lorion03vel | ... | all
#   [cible-make]    cible exécutée sur la VM (défaut : up)
#   --with-secrets  pousse aussi .env et secrets/ (par défaut exclus :
#                   les fichiers présents sur la VM font foi)
#
# Exemples :
#   deploy/deploy.sh lorion03vel            # rsync + make up
#   deploy/deploy.sh lorion01vel ps         # état des services
#   deploy/deploy.sh all                    # déploie toutes les VMs
#
# Configuration : deploy/hosts.env (non versionné), copié depuis
# deploy/hosts.env.example. Définit la destination SSH de chaque VM
# (DEPLOY_HOST_<vm>) et le chemin du dépôt côté VM (REMOTE_DIR).
# DEPLOY_HOST_<vm>=local => exécution locale (pas de SSH), pour la VM
# qui héberge déjà ce dépôt.
#
# Multi-opérateur : hosts.env est sourcé par bash — utiliser $USER dans
# DEPLOY_HOST_<vm> (ex. $USER@10.10.1.12) pour que chacun se connecte
# avec SON compte VM (c'est alors SON mot de passe que ssh-copy-id
# demande). REMOTE_DIR relatif (défaut : autoCOREBIB/orion-lab-stack)
# est résolu sous le home de cet utilisateur côté VM.
#
# Ce qui est poussé : common.mk + le dossier de la VM, HORS artefacts
# d'exécution (data/, logs/, __pycache__) qui appartiennent à la VM.
#
# VM sans make : les cibles courantes (up, down, ps, purge) sont émulées
# en docker compose directement — installer make sur la VM n'est pas requis.
#
# Clé SSH : installée automatiquement au premier contact avec une VM
# (ssh-copy-id, mot de passe demandé une seule fois) ; les passages
# suivants détectent la clé déjà en place et n'affichent rien.
#
# REMOTE_DIR : créé automatiquement au premier deploy. Si le parent
# appartient à root (ex. /data en 755), une création via sudo est tentée
# en interactif (mot de passe demandé une fois, comme ssh-copy-id).
# ============================================================
# Si un script échoue, on arrête tout de suite (set -e), on ne laisse pas de variables non initialisées (set -u)
# et on ne masque pas les erreurs dans les pipes (set -o pipefail).
set -euo pipefail

# REPO_ROOT : chemin absolu du dépôt (dossier parent de deploy/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOSTS_FILE="$REPO_ROOT/deploy/hosts.env"

# die() : affiche un message d'erreur et quitte avec code 1
#
die() { echo "deploy.sh: $*" >&2; exit 1; }

# ensure_ssh_key() : garantit l'authentification par clé vers la VM.
# Teste d'abord une connexion sans mot de passe (BatchMode) ; si elle échoue,
# installe la clé publique avec ssh-copy-id — c'est le seul moment où le mot
# de passe de la VM est demandé (une fois par VM, au premier déploiement).
ensure_ssh_key() {
  local host="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$host" true 2>/dev/null && return 0
  echo "── $host : authentification par clé indisponible, installation via ssh-copy-id ──"
  ssh-copy-id "$host" || die "$host : échec ssh-copy-id (mot de passe incorrect ou hôte injoignable)"
}

# ensure_remote_dir() : crée REMOTE_DIR sur la VM. Si l'utilisateur SSH ne
# peut pas (parent appartenant à root, ex. /data en root:755), tente une
# création via sudo en interactif — le mot de passe est demandé une fois,
# comme pour ssh-copy-id — puis donne la propriété à l'utilisateur SSH.
ensure_remote_dir() {
  local vm="$1" host="$2"
  ssh "$host" "mkdir -p '$REMOTE_DIR'" 2>/dev/null && return 0
  echo "── $vm : $REMOTE_DIR non créable par l'utilisateur SSH, tentative via sudo ──"
  ssh -t "$host" "sudo install -d -o \"\$(id -un)\" -g \"\$(id -gn)\" '$REMOTE_DIR'" || {
    echo "$vm : impossible de créer $REMOTE_DIR — exécuter une fois sur la VM :" >&2
    echo "$vm :   sudo install -d -o \"\$USER\" -g \"\$(id -gn)\" '$REMOTE_DIR'" >&2
    return 1
  }
}

# compose_fallback() : équivalent docker compose d'une cible make, pour les
# VMs où make n'est pas installé. Les cibles de common.mk sont assez simples
# pour être émulées ; le réseau suit la convention NET = <vm>-network.
# Retourne 1 si la cible n'a pas d'équivalent (il faudra installer make).
compose_fallback() {
  local net="$1-network"
  case "$TARGET" in
    ps)    echo "docker compose ps" ;;
    down)  echo "docker compose down" ;;
    up)    echo "docker network inspect '$net' >/dev/null 2>&1 || docker network create '$net'; docker compose up -d --build" ;;
    purge) echo "docker compose down; docker network rm '$net'" ;;
    *)     return 1 ;;
  esac
}

# On vérifie qu'on a au moins un argument (le nom de la VM ou "all"), sinon on affiche l'usage.
[ $# -ge 1 ] || die "usage : deploy/deploy.sh <vm-dir|all> [cible-make] [--with-secrets]"
# On récupère le nom de la VM (ou "all") et on décale les arguments pour traiter les options suivantes.
VM="$1"; shift

# TARGET : cible make à exécuter sur la VM (défaut : up)
# WITH_SECRETS : 1 si on doit pousser les secrets, 0 sinon (défaut)
# On parcourt les arguments restants pour récupérer la cible make et l'option --with-secrets.
TARGET="up"
WITH_SECRETS=0
for arg in "$@"; do
  case "$arg" in
    --with-secrets) WITH_SECRETS=1 ;;
    *) TARGET="$arg" ;;
  esac
done

[ -f "$HOSTS_FILE" ] || die "config manquante : copier deploy/hosts.env.example en deploy/hosts.env et renseigner les hôtes"
# shellcheck source=/dev/null
source "$HOSTS_FILE"
# Défaut relatif : résolu sous le $HOME de l'utilisateur SSH sur la VM.
# Chaque opérateur déploie ainsi dans son propre home (~/autoCOREBIB/...),
# avec son propre compte et son propre mot de passe — aucun chemin en dur.
REMOTE_DIR="${REMOTE_DIR:-autoCOREBIB/orion-lab-stack}"
# On tolère un slash final dans hosts.env (sinon chemins en "//" plus bas).
REMOTE_DIR="${REMOTE_DIR%/}"

deploy_one() {
  local vm="$1"
  local dir="$REPO_ROOT/$vm"
  [ -f "$dir/Makefile" ] || die "$vm : pas de Makefile dans $dir"

  # DEPLOY_HOST_lorion03vel (les tirets deviennent des underscores)
  local var="DEPLOY_HOST_${vm//-/_}"
  # On récupère la valeur de la variable dont le nom est contenu dans $var (ex. DEPLOY_HOST_lorion03vel) ; si elle n'est pas définie, on quitte avec une erreur.
  local host="${!var:-}"
  [ -n "$host" ] || die "$vm : $var non défini dans deploy/hosts.env"

  if [ "$host" = "local" ]; then
    echo "── $vm (local) : make $TARGET ──"
    make -C "$dir" "$TARGET"
    return
  fi

  ensure_ssh_key "$host"

  # Le code n'est poussé (rsync) que pour un déploiement (`up`) ; les autres
  # cibles (down, purge, ps, ...) sont de pures commandes de contrôle à distance.
  if [ "$TARGET" = "up" ]; then
    echo "── $vm -> $host : rsync + make $TARGET ──"
    local excludes=(
      --exclude '.git' --exclude '__pycache__' --exclude '*.pyc'
      --exclude 'data/' --exclude 'logs/'
    )
    if [ "$WITH_SECRETS" -eq 0 ]; then
      excludes+=(--exclude '.env' --exclude 'secrets/')
    fi

    # EXTRA_SYNC_<vm> (hosts.env) : dossiers racine supplémentaires à pousser
    # (ex. orion-stack-documentation, référencé par l'include de lorion03vel).
    local extra_var="EXTRA_SYNC_${vm//-/_}"
    local extras="${!extra_var:-}"
    local paths=("$REPO_ROOT/./common.mk" "$REPO_ROOT/./$vm")
    local extra
    for extra in $extras; do
      [ -e "$REPO_ROOT/$extra" ] || die "$vm : EXTRA_SYNC introuvable : $extra"
      paths+=("$REPO_ROOT/./$extra")
    done

    # Échecs explicites : en mode `all`, errexit est neutralisé pour cette
    # fonction (appel via `||`), il ne faut donc rien laisser passer en silence.
    ensure_remote_dir "$vm" "$host" || return 1
    # -R (--relative) préserve les chemins common.mk et <vm>/ sous REMOTE_DIR.
    # Multi-utilisateurs (hosts.env en $USER@... : chacun déploie sous SON
    # compte, les fichiers distants appartiennent au dernier déployeur) :
    #   -O                     : ne pas re-tamponner les dossiers (mtime d'un
    #                            dossier appartenant à un collègue = EPERM)
    #   --chmod=Dg+rwxs,Fg+rw  : ce qu'on crée reste écrivable par le groupe
    #                            (setgid sur les dossiers), pour le déployeur
    #                            suivant. Prérequis one-shot déjà appliqué sur
    #                            les VMs : chmod -R g+rwX + setgid sur l'arbre.
    rsync -azRO --chmod=Dg+rwxs,Fg+rw "${excludes[@]}" \
      -e ssh \
      "${paths[@]}" \
      "$host:$REMOTE_DIR/" || { echo "$vm : échec rsync vers $host" >&2; return 1; }
  else
    echo "── $vm -> $host : make $TARGET ──"
  fi
  # Si make est absent sur la VM (image minimale), on retombe sur
  # l'équivalent docker compose de la cible.
  local fallback
  fallback="$(compose_fallback "$vm")" || \
    fallback="echo \"$vm : make absent sur la VM et cible '$TARGET' sans équivalent docker compose (installer make)\" >&2; exit 127"
  ssh "$host" "cd '$REMOTE_DIR/$vm' 2>/dev/null || \
      { echo \"$vm : $REMOTE_DIR/$vm absent sur la VM (jamais déployée ? lancer make deploy VM=$vm)\" >&2; exit 1; }; \
    if command -v make >/dev/null 2>&1; then make '$TARGET'; \
    else $fallback; fi"
}

if [ "$VM" = "all" ]; then
  found=0
  failed=()
  for dir in "$REPO_ROOT"/lorion*vel; do
    [ -f "$dir/Makefile" ] || continue
    found=1
    # Une VM en échec n'interrompt pas les autres ; on récapitule à la fin.
    deploy_one "$(basename "$dir")" || failed+=("$(basename "$dir")")
  done
  [ "$found" -eq 1 ] || die "aucune stack VM avec Makefile trouvée"
  [ "${#failed[@]}" -eq 0 ] || die "échec sur : ${failed[*]}"
else
  deploy_one "$VM"
fi

echo "── OK ──"

#!/usr/bin/env bash
# ============================================================
# manage-users.sh — Gestion des utilisateurs Grafana (API HTTP)
# Usage : ./manage-users.sh [commande] [options]
#
# Même esprit que clickhouse/manage-users.sh (lorion03vel) : l'admin est le
# seul à créer des comptes (l'auto-inscription est désactivée), chaque compte
# naît Viewer et est promu explicitement si besoin.
#
# Commandes :
#   list                          Liste les utilisateurs (id, login, rôle, dernier accès)
#   create <login> [email]        Crée un utilisateur (mot de passe généré, rôle Viewer)
#   delete <login>                Supprime un utilisateur
#   reset-password <login>        Régénère le mot de passe d'un utilisateur
#   set-role <login> <role>       Change le rôle org : Viewer | Editor | Admin
#
# S'exécute depuis le poste d'admin ou la VM : l'URL vient de GRAFANA_URL,
# sinon de GRAFANA_ROOT_URL (.env), sinon http://localhost:<port>.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
    set +a
fi

# URL de l'API : GRAFANA_URL si défini, sinon GRAFANA_ROOT_URL (.env) —
# permet de lancer le script depuis le poste d'admin, pas seulement la VM.
GRAFANA_URL="${GRAFANA_URL:-${GRAFANA_ROOT_URL:-http://localhost:${GRAFANA_HTTP_PORT:-3000}}}"
# Slash final toléré (sinon "//api/..." -> redirection 302 au lieu de l'API).
GRAFANA_URL="${GRAFANA_URL%/}"
ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
ADMIN_PASSWORD_FILE="${GRAFANA_ADMIN_PASSWORD_FILE:-secrets/grafana_admin_password}"
[[ "${ADMIN_PASSWORD_FILE}" != /* ]] && ADMIN_PASSWORD_FILE="${SCRIPT_DIR}/${ADMIN_PASSWORD_FILE}"
[[ -f "${ADMIN_PASSWORD_FILE}" ]] || { echo "ERREUR : secret admin introuvable : ${ADMIN_PASSWORD_FILE}" >&2; exit 1; }
ADMIN_PASS="$(< "${ADMIN_PASSWORD_FILE}")"

# --noproxy '*' : Grafana est dans le lab, on ne passe jamais par le proxy
# d'entreprise. -sS + --fail : une erreur HTTP ou réseau s'affiche clairement
# au lieu de produire un corps vide (et un traceback du parseur JSON).
api() { # api <méthode> <chemin> [corps-json]
    local method="$1" path="$2" body="${3:-}"
    local args=(-sS --noproxy '*' --fail-with-body \
                -u "${ADMIN_USER}:${ADMIN_PASS}" -X "$method" \
                -H 'Content-Type: application/json' "${GRAFANA_URL}${path}")
    [[ -n "$body" ]] && args+=(-d "$body")
    curl "${args[@]}" || die "échec $method ${GRAFANA_URL}${path} (voir message curl ci-dessus)"
}

die() { echo "manage-users.sh: $*" >&2; exit 1; }

# user_id <login> : résout l'id numérique d'un login (erreur si absent)
user_id() {
    local id
    id=$(api GET "/api/users/lookup?loginOrEmail=$1" | python3 -c 'import json,sys
d = json.load(sys.stdin); print(d.get("id", ""))')
    [[ -n "$id" ]] || die "utilisateur inconnu : $1"
    echo "$id"
}

gen_password() { openssl rand -base64 18 | tr -d '/+=' | head -c 20; }

cmd_list() {
    api GET "/api/org/users" | python3 -c 'import json,sys
for u in json.load(sys.stdin):
    print("{:>4}  {:<20} {:<8} dernier accès : {}".format(
        u["userId"], u["login"], u["role"], u.get("lastSeenAtAge", "?")))'
}

cmd_create() {
    local login="$1" email="${2:-$1@lab.local}" pw
    pw="$(gen_password)"
    api POST "/api/admin/users" \
        "{\"login\":\"$login\",\"email\":\"$email\",\"name\":\"$login\",\"password\":\"$pw\"}" \
        | python3 -m json.tool
    echo "Mot de passe initial de '$login' : $pw"
    echo "(rôle : Viewer — le promouvoir avec : $0 set-role $login Editor)"
}

cmd_delete() {
    local id; id="$(user_id "$1")"
    api DELETE "/api/admin/users/$id" | python3 -m json.tool
}

cmd_reset_password() {
    local id pw; id="$(user_id "$1")"; pw="$(gen_password)"
    api PUT "/api/admin/users/$id/password" "{\"password\":\"$pw\"}" | python3 -m json.tool
    echo "Nouveau mot de passe de '$1' : $pw"
}

cmd_set_role() {
    local role="$2"
    case "$role" in Viewer|Editor|Admin) ;; *) die "rôle invalide : $role (Viewer|Editor|Admin)" ;; esac
    local id; id="$(user_id "$1")"
    api PATCH "/api/org/users/$id" "{\"role\":\"$role\"}" | python3 -m json.tool
}

usage() {
    sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
    list)           cmd_list ;;
    create)         [[ $# -ge 2 ]] || die "usage : $0 create <login> [email]"; cmd_create "$2" "${3:-}" ;;
    delete)         [[ $# -ge 2 ]] || die "usage : $0 delete <login>"; cmd_delete "$2" ;;
    reset-password) [[ $# -ge 2 ]] || die "usage : $0 reset-password <login>"; cmd_reset_password "$2" ;;
    set-role)       [[ $# -ge 3 ]] || die "usage : $0 set-role <login> <Viewer|Editor|Admin>"; cmd_set_role "$2" "$3" ;;
    -h|--help|"")   usage ;;
    *)              die "commande inconnue : $1 (voir --help)" ;;
esac

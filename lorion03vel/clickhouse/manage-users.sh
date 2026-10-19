#!/usr/bin/env bash
# ============================================================
# manage_users.sh — Gestion dynamique des utilisateurs ClickHouse
# Usage : ./manage_users.sh [commande] [options]
# ============================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────
# Charge les variables depuis le .env voisin (mêmes valeurs que le compose).
# Les variables déjà exportées dans l'environnement restent prioritaires.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
    set +a
fi

# Les requêtes sont exécutées via le client natif DANS le conteneur ClickHouse
# (docker exec). Cela évite l'interface HTTP, le mapping de ports de l'hôte et
# le proxy d'entreprise — qui posaient problème en mode curl.
CH_CONTAINER="${CLICKHOUSE_CONTAINER:-lorion03vel-clickhouse}"
CH_ADMIN="${CLICKHOUSE_ADMIN_USER:-admin}"

# Mot de passe admin : priorité au fichier secret (*_FILE) s'il est défini.
# Le chemin peut être relatif (résolu par rapport au dossier du script).
if [[ -n "${CLICKHOUSE_ADMIN_PASSWORD_FILE:-}" ]]; then
    _pwfile="${CLICKHOUSE_ADMIN_PASSWORD_FILE}"
    [[ "${_pwfile}" != /* ]] && _pwfile="${SCRIPT_DIR}/${_pwfile}"
    if [[ -f "${_pwfile}" ]]; then
        CLICKHOUSE_ADMIN_PASSWORD="$(< "${_pwfile}")"
    else
        echo "ERREUR : fichier secret introuvable : ${_pwfile}" >&2
        exit 1
    fi
fi
CH_ADMIN_PASS="${CLICKHOUSE_ADMIN_PASSWORD}"

# ── Couleurs ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helpers ──────────────────────────────────────────────────
info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
success() { echo -e "${GREEN}✔${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
error()   { echo -e "${RED}✖${NC}  $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}"; echo -e "${CYAN}$(printf '─%.0s' {1..50})${NC}"; }

# Exécuter une requête SQL sur ClickHouse via le client natif du conteneur
ch_query() {
    local sql="$1"
    local response
    response=$(docker exec "${CH_CONTAINER}" \
        clickhouse-client \
        --user "${CH_ADMIN}" \
        --password "${CH_ADMIN_PASS}" \
        --query "${sql}" 2>&1) || {
        error "Requête ClickHouse échouée : ${response}"
        exit 1
    }
    echo "${response}"
}

# Vérifier la connexion
check_connection() {
    info "Vérification de la connexion au conteneur ${CH_CONTAINER}…"
    ch_query "SELECT 1" > /dev/null
    success "Connecté à ClickHouse (conteneur ${CH_CONTAINER})"
}

# ── Lister les rôles disponibles ─────────────────────────────
list_roles() {
    ch_query "SELECT name FROM system.roles ORDER BY name" 2>/dev/null || echo ""
}

# ── Lister les bases de données ──────────────────────────────
list_databases() {
    ch_query "SELECT name FROM system.databases WHERE name NOT IN ('system','information_schema','INFORMATION_SCHEMA') ORDER BY name"
}

# ============================================================
# COMMANDES
# ============================================================

# ── Créer un utilisateur ─────────────────────────────────────
cmd_create() {
    header "➕ Créer un utilisateur"

    # Nom d'utilisateur
    read -rp "  Nom d'utilisateur        : " username
    [[ -z "$username" ]] && { error "Le nom ne peut pas être vide."; exit 1; }

    # Vérifier s'il existe déjà
    existing=$(ch_query "SELECT count() FROM system.users WHERE name = '${username}'" | tr -d '[:space:]')
    if [[ "$existing" != "0" ]]; then
        error "L'utilisateur '${username}' existe déjà."
        exit 1
    fi

    # Mot de passe
    read -rsp "  Mot de passe             : " password; echo
    read -rsp "  Confirmer le mot de passe: " password2; echo
    [[ "$password" != "$password2" ]] && { error "Les mots de passe ne correspondent pas."; exit 1; }
    [[ ${#password} -lt 8 ]]         && { error "Le mot de passe doit faire au moins 8 caractères."; exit 1; }

    # Afficher les rôles disponibles
    echo ""
    info "Rôles disponibles :"
    roles=$(list_roles)
    if [[ -z "$roles" ]]; then
        warn "Aucun rôle trouvé. L'utilisateur sera créé sans rôle."
        role=""
    else
        echo "$roles" | nl -w2 -s') '
        read -rp "  Numéro du rôle (Entrée pour aucun) : " role_num
        if [[ -n "$role_num" ]]; then
            role=$(echo "$roles" | sed -n "${role_num}p")
            [[ -z "$role" ]] && { error "Numéro de rôle invalide."; exit 1; }
        else
            role=""
        fi
    fi

    # Base de données par défaut
    echo ""
    info "Bases de données disponibles :"
    list_databases | nl -w2 -s') '
    read -rp "  Base de données par défaut (Entrée pour toutes) : " db_num
    if [[ -n "$db_num" ]]; then
        default_db=$(list_databases | sed -n "${db_num}p")
        [[ -z "$default_db" ]] && { error "Numéro de base invalide."; exit 1; }
    else
        default_db=""
    fi

    # Restriction d'hôte
    echo ""
    echo "  Restriction d'hôte :"
    echo "    1) Tous les hôtes (défaut)"
    echo "    2) Localhost uniquement"
    echo "    3) Adresse IP spécifique"
    read -rp "  Choix [1-3] : " host_choice
    case "${host_choice:-1}" in
        1) host_clause="HOST ANY" ;;
        2) host_clause="HOST LOCAL" ;;
        3)
            read -rp "  Adresse IP : " custom_ip
            host_clause="HOST IP '${custom_ip}'"
            ;;
        *) host_clause="HOST ANY" ;;
    esac

    # Confirmation
    echo ""
    echo -e "  ${BOLD}Récapitulatif :${NC}"
    echo "    Utilisateur : ${username}"
    echo "    Rôle        : ${role:-aucun}"
    echo "    Base        : ${default_db:-toutes}"
    echo "    Hôte        : ${host_clause}"
    read -rp "  Confirmer la création ? [o/N] : " confirm
    [[ "${confirm,,}" != "o" ]] && { warn "Annulé."; exit 0; }

    # Création
    sql="CREATE USER \`${username}\` IDENTIFIED WITH sha256_password BY '${password}' ${host_clause}"
    [[ -n "$default_db" ]] && sql+=" DEFAULT DATABASE \`${default_db}\`"
    ch_query "$sql"

    # Attribution du rôle
    if [[ -n "$role" ]]; then
        ch_query "GRANT \`${role}\` TO \`${username}\`"
        ch_query "ALTER USER \`${username}\` DEFAULT ROLE \`${role}\`"
    fi

    success "Utilisateur '${username}' créé avec succès !"
}

# ── Supprimer un utilisateur ─────────────────────────────────
cmd_delete() {
    header "🗑  Supprimer un utilisateur"

    users=$(ch_query "SELECT name FROM system.users WHERE name NOT IN ('default','admin') ORDER BY name")
    [[ -z "$users" ]] && { warn "Aucun utilisateur supprimable trouvé."; exit 0; }

    echo "$users" | nl -w2 -s') '
    read -rp "  Numéro de l'utilisateur à supprimer : " num
    username=$(echo "$users" | sed -n "${num}p")
    [[ -z "$username" ]] && { error "Numéro invalide."; exit 1; }

    read -rp "  Supprimer '${username}' ? [o/N] : " confirm
    [[ "${confirm,,}" != "o" ]] && { warn "Annulé."; exit 0; }

    ch_query "DROP USER \`${username}\`"
    success "Utilisateur '${username}' supprimé."
}

# ── Modifier le mot de passe ──────────────────────────────────
cmd_passwd() {
    header "🔑 Modifier un mot de passe"

    users=$(ch_query "SELECT name FROM system.users ORDER BY name")
    echo "$users" | nl -w2 -s') '
    read -rp "  Numéro de l'utilisateur : " num
    username=$(echo "$users" | sed -n "${num}p")
    [[ -z "$username" ]] && { error "Numéro invalide."; exit 1; }

    read -rsp "  Nouveau mot de passe             : " password; echo
    read -rsp "  Confirmer le nouveau mot de passe: " password2; echo
    [[ "$password" != "$password2" ]] && { error "Les mots de passe ne correspondent pas."; exit 1; }
    [[ ${#password} -lt 8 ]]         && { error "Minimum 8 caractères requis."; exit 1; }

    ch_query "ALTER USER \`${username}\` IDENTIFIED WITH sha256_password BY '${password}'"
    success "Mot de passe de '${username}' mis à jour."
}

# ── Gérer les rôles d'un utilisateur ─────────────────────────
cmd_roles() {
    header "🎭 Gérer les rôles"

    echo "  1) Attribuer un rôle"
    echo "  2) Révoquer un rôle"
    read -rp "  Choix [1-2] : " action

    users=$(ch_query "SELECT name FROM system.users ORDER BY name")
    echo ""
    info "Utilisateurs :"
    echo "$users" | nl -w2 -s') '
    read -rp "  Numéro de l'utilisateur : " u_num
    username=$(echo "$users" | sed -n "${u_num}p")
    [[ -z "$username" ]] && { error "Numéro invalide."; exit 1; }

    roles=$(list_roles)
    [[ -z "$roles" ]] && { warn "Aucun rôle disponible."; exit 0; }

    echo ""
    info "Rôles disponibles :"
    echo "$roles" | nl -w2 -s') '
    read -rp "  Numéro du rôle : " r_num
    role=$(echo "$roles" | sed -n "${r_num}p")
    [[ -z "$role" ]] && { error "Numéro de rôle invalide."; exit 1; }

    case "$action" in
        1)
            ch_query "GRANT \`${role}\` TO \`${username}\`"
            success "Rôle '${role}' attribué à '${username}'."
            ;;
        2)
            ch_query "REVOKE \`${role}\` FROM \`${username}\`"
            success "Rôle '${role}' révoqué pour '${username}'."
            ;;
        *)
            error "Choix invalide."
            exit 1
            ;;
    esac
}

# ── Créer un rôle ─────────────────────────────────────────────
cmd_create_role() {
    header "🎭 Créer un rôle"

    read -rp "  Nom du rôle : " rolename
    [[ -z "$rolename" ]] && { error "Le nom ne peut pas être vide."; exit 1; }

    echo ""
    info "Bases de données disponibles :"
    list_databases | nl -w2 -s') '
    read -rp "  Numéro de la base (Entrée pour toutes) : " db_num
    if [[ -n "$db_num" ]]; then
        db=$(list_databases | sed -n "${db_num}p")
        db_target="\`${db}\`.*"
    else
        db_target="*.*"
    fi

    echo ""
    echo "  Permissions à accorder :"
    echo "    1) SELECT uniquement (lecture)"
    echo "    2) SELECT + INSERT (lecture/écriture)"
    echo "    3) ALL (administration complète)"
    read -rp "  Choix [1-3] : " perm_choice

    case "$perm_choice" in
        1) privileges="SELECT" ;;
        2) privileges="SELECT, INSERT" ;;
        3) privileges="ALL" ;;
        *) error "Choix invalide."; exit 1 ;;
    esac

    ch_query "CREATE ROLE IF NOT EXISTS \`${rolename}\`"
    ch_query "GRANT ${privileges} ON ${db_target} TO \`${rolename}\`"
    success "Rôle '${rolename}' créé avec les permissions '${privileges}' sur ${db_target}."
}

# ── Lister utilisateurs et leurs rôles ───────────────────────
cmd_list() {
    header "👥 Utilisateurs et rôles"
    result=$(ch_query "
        SELECT
            u.name              AS utilisateur,
            u.auth_type         AS authentification,
            groupArray(r.role_name) AS roles
        FROM system.users u
        LEFT JOIN system.role_grants r ON r.user_name = u.name
        GROUP BY u.name, u.auth_type
        ORDER BY u.name
        FORMAT PrettyCompact
    ")
    echo "$result"

    header "🎭 Rôles et permissions"
    result2=$(ch_query "
        SELECT role_name, access_type, database, table
        FROM system.grants
        WHERE role_name != ''
        ORDER BY role_name, access_type
        FORMAT PrettyCompact
    ")
    echo "$result2"
}

# ── Lister les bases de données ──────────────────────────────
cmd_databases() {
    header "🗄  Bases de données"
    result=$(ch_query "
        SELECT
            d.name   AS base,
            d.engine AS moteur,
            countIf(t.name != '')                 AS tables,
            formatReadableSize(sum(t.total_bytes)) AS taille
        FROM system.databases AS d
        LEFT JOIN system.tables AS t ON t.database = d.name
        GROUP BY d.name, d.engine
        ORDER BY d.name
        FORMAT PrettyCompact
    ")
    echo "$result"
}

# ── Lister les tables (d'une base ou de toutes) ──────────────
cmd_tables() {
    header "📋 Tables"

    info "Bases de données disponibles :"
    list_databases | nl -w2 -s') '
    read -rp "  Numéro de la base (Entrée pour toutes) : " db_num
    if [[ -n "$db_num" ]]; then
        db=$(list_databases | sed -n "${db_num}p")
        [[ -z "$db" ]] && { error "Numéro de base invalide."; exit 1; }
        where="database = '${db}'"
    else
        where="database NOT IN ('system','information_schema','INFORMATION_SCHEMA')"
    fi

    result=$(ch_query "
        SELECT
            database AS base,
            name     AS nom_table,
            engine   AS moteur,
            formatReadableQuantity(ifNull(total_rows, 0)) AS lignes,
            formatReadableSize(ifNull(total_bytes, 0))    AS taille
        FROM system.tables
        WHERE ${where}
        ORDER BY database, name
        FORMAT PrettyCompact
    ")
    [[ -z "$result" ]] && { warn "Aucune table trouvée."; return; }
    echo "$result"
}

# ── Menu interactif ───────────────────────────────────────────
cmd_menu() {
    check_connection

    while true; do
        header "⚙️  Gestion ClickHouse"
        echo "    1) Lister les utilisateurs et rôles"
        echo "    2) Lister les bases de données"
        echo "    3) Lister les tables"
        echo "    4) Créer un utilisateur"
        echo "    5) Supprimer un utilisateur"
        echo "    6) Modifier un mot de passe"
        echo "    7) Gérer les rôles d'un utilisateur"
        echo "    8) Créer un rôle personnalisé"
        echo "    0) Quitter"
        echo ""
        read -rp "  Votre choix : " choice

        case "$choice" in
            1) cmd_list ;;
            2) cmd_databases ;;
            3) cmd_tables ;;
            4) cmd_create ;;
            5) cmd_delete ;;
            6) cmd_passwd ;;
            7) cmd_roles ;;
            8) cmd_create_role ;;
            0) echo ""; info "Au revoir !"; exit 0 ;;
            *) warn "Choix invalide." ;;
        esac
    done
}

# ── Point d'entrée ────────────────────────────────────────────
usage() {
    echo ""
    echo -e "  ${BOLD}Usage :${NC} $0 [commande]"
    echo ""
    echo "  Commandes :"
    echo "    (aucune)      Menu interactif (défaut)"
    echo "    list          Lister les utilisateurs et rôles"
    echo "    databases     Lister les bases de données"
    echo "    tables        Lister les tables (d'une base ou de toutes)"
    echo "    create        Créer un utilisateur"
    echo "    delete        Supprimer un utilisateur"
    echo "    passwd        Modifier un mot de passe"
    echo "    roles         Gérer les rôles d'un utilisateur"
    echo "    create-role   Créer un rôle personnalisé"
    echo ""
    echo "  Variables d'environnement :"
    echo "    CLICKHOUSE_CONTAINER      (défaut: lorion03vel-clickhouse)"
    echo "    CLICKHOUSE_ADMIN_USER     (défaut: admin)"
    echo "    CLICKHOUSE_ADMIN_PASSWORD (défaut: pwd!)"
    echo ""
}

case "${1:-menu}" in
    menu)        cmd_menu ;;
    list)        check_connection; cmd_list ;;
    databases|db) check_connection; cmd_databases ;;
    tables)      check_connection; cmd_tables ;;
    create)      check_connection; cmd_create ;;
    delete)      check_connection; cmd_delete ;;
    passwd)      check_connection; cmd_passwd ;;
    roles)       check_connection; cmd_roles ;;
    create-role) check_connection; cmd_create_role ;;
    -h|--help)   usage ;;
    *)           error "Commande inconnue : ${1}"; usage; exit 1 ;;
esac
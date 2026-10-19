#!/usr/bin/env bash
# ============================================================
# load_clickhouse.sh — Charge les CSV gobgp dans ClickHouse (lorion03vel)
#
# Connexion en protocole natif (port 9000) directement depuis cette VM :
# évite le proxy d'entreprise (http_proxy) qui casse le mode HTTP/curl,
# et évite docker exec puisque ClickHouse tourne sur une VM séparée.
#
# Pas de TRUNCATE : les tables sont en ReplacingMergeTree(Age), on
# insère à chaque cycle et ClickHouse déduplique par clé au fil des merges.
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOBGP_DIR="$(dirname "${SCRIPT_DIR}")"
DATA_DIR="${GOBGP_DIR}/data"
PASSWORD_FILE="${GOBGP_DIR}/secrets/ch_gobgp_password"

## "lorion03vel" est stale dans /etc/hosts de cette VM (pointe vers une autre
## instance sans l'utilisateur gobgp_writer) -> IP directe de la vraie instance.
CH_HOST="${CH_HOST:-10.10.3.141}"
CH_PORT="${CH_PORT:-9000}"
CH_USER="${CH_USER:-gobgp_writer}"

if [[ ! -f "${PASSWORD_FILE}" ]]; then
    echo "ERREUR : fichier secret introuvable : ${PASSWORD_FILE}" >&2
    echo "Créez-le avec le mot de passe de l'utilisateur ${CH_USER} (voir schemas/00_setup.sql)." >&2
    exit 1
fi
CH_PASSWORD="$(< "${PASSWORD_FILE}")"

# fichier CSV -> table gobgp cible (noms définis dans schemas/*.sql)
declare -A FILE_TO_TABLE=(
    ["PROD__pull_bgp_ls_link.csv"]="bgp_ls_links"
    ["PROD__pull_bgp_ls_node.csv"]="bgp_ls_nodes"
    ["PROD__pull_bgp_ls_prefixV4.csv"]="bgp_ls_prefixV4"
    ["PROD__pull_bgp_ls_prefixV6.csv"]="bgp_ls_prefixV6"
    ["PROD__PULL_SAFI_LINK_STATE_LINK.csv"]="SAFI_LINK_STATE_LINK"
    ["PROD__PULL_SAFI_LINK_STATE_NODE.csv"]="SAFI_LINK_STATE_NODE"
    ["PROD__PULL_SAFI_LINK_STATE_PREFIXE_V4.csv"]="SAFI_LINK_STATE_PREFIXE_V4"
    ["PROD__PULL_SAFI_LINK_STATE_PREFIXE_V6.csv"]="SAFI_LINK_STATE_PREFIXE_V6"
)

ch_client() {
    clickhouse-client --host "${CH_HOST}" --port "${CH_PORT}" \
        --user "${CH_USER}" --password "${CH_PASSWORD}" "$@"
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Début du chargement gobgp → ClickHouse (${CH_HOST}:${CH_PORT})"

status=0
for csv_file in "${!FILE_TO_TABLE[@]}"; do
    table="${FILE_TO_TABLE[$csv_file]}"
    csv_path="${DATA_DIR}/${csv_file}"

    if [[ ! -f "${csv_path}" ]]; then
        echo "  [SKIP] ${csv_file} introuvable"
        continue
    fi

    rows=$(($(wc -l < "${csv_path}") - 1))
    if ch_client --async_insert=0 --format_csv_delimiter=';' \
        --query "INSERT INTO gobgp.${table} FORMAT CSVWithNames" < "${csv_path}"; then
        echo "  [OK]   ${csv_file} → gobgp.${table} (${rows} lignes)"
    else
        echo "  [FAIL] ${csv_file} → gobgp.${table}" >&2
        status=1
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fin du chargement (statut=${status})"
exit "${status}"

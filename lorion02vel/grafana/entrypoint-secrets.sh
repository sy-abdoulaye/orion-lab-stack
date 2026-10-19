#!/bin/sh
# ============================================================
# entrypoint-secrets.sh — exporte les secrets fichiers en variables d'env.
#
# Grafana ne lit la convention `__FILE` que pour ses propres options GF_*.
# Les variables consommées par l'interpolation des fichiers de provisioning
# (ex. $CLICKHOUSE_GRAFANA_PASSWORD dans datasources/clickhouse.yml) doivent
# être de vraies variables d'environnement : on les charge ici depuis les
# fichiers montés par `secrets:`, puis on rend la main à l'entrypoint officiel.
# ============================================================
set -eu

# export_file_var VAR : si VAR__FILE est défini et pointe un fichier lisible,
# exporte VAR avec son contenu.
export_file_var() {
  var="$1"
  file_var="${var}__FILE"
  file="$(eval "printf '%s' \"\${${file_var}:-}\"")"
  if [ -n "$file" ] && [ -r "$file" ]; then
    export "${var}=$(cat "$file")"
  fi
}

export_file_var CLICKHOUSE_GRAFANA_PASSWORD

exec /run.sh "$@"

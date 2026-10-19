#!/bin/sh
set -eu

if [ -f /run/secrets/ch_gobgp_password ]; then
    CLICKHOUSE_PASSWORD="$(cat /run/secrets/ch_gobgp_password)"
    export CLICKHOUSE_PASSWORD
else
    echo "ERREUR : /run/secrets/ch_gobgp_password introuvable (secret non monté)" >&2
    exit 1
fi

exec vector --config /etc/vector/vector.yaml

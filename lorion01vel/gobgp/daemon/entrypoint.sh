#!/bin/sh
# ──────────────────────────────────────────────────────
# entrypoint.sh
# --api-hosts force gobgpd à écouter gRPC sur 50052
# pour coexister avec le gobgpd prod sur 50051
# ──────────────────────────────────────────────────────
set -e

# echo "[entrypoint] Démarrage du daemon cron..."
# /usr/sbin/crond -b -l 8 -L /var/log/gobgp/cron.log

echo "[entrypoint] Démarrage de gobgpd..."
exec /opt/gobgp/gobgpd \
    -f /opt/gobgp/gobgpd_all.conf \
    --api-hosts ":50051" \
    --log-plain \
    -l info
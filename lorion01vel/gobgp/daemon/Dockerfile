# ─────────────────────────────────────────────────────────
# Image gobgpd  –  sans accès internet (pas de apk add)
#
# Structure attendue dans le projet avant de builder :
#
#   opt-gobgp/
#   ├── gobgpd                    ← binaire daemon (obligatoire)
#   ├── gobgp                     ← binaire CLI    (optionnel)
#   └── bin/
#       ├── prod__pull_safi_LINK_STATE   ← script cron (obligatoire)
#       └── prod__pull_bgp_ls            ← script cron (obligatoire)
#   gobgpd_all.conf               ← config BGP-LS  (obligatoire)
#  gobgpd/
#   └── entrypoint.sh             ← script d'entrypoint
# ─────────────────────────────────────────────────────────
# FROM registry.example.com/dockerhub/library/alpine:3.20
FROM registry.example.com/dockerhub/library/ubuntu:22.04

# Pas de apk add — pas d'accès internet sur ce host
# Alpine de base contient déjà : sh, mkdir, chmod, ln, echo

# Fuseau horaire (sans tzdata, on passe par la variable d'env)
ENV TZ=Europe/Paris

# ── Binaires ────────────────────────────────────────────
COPY bin/gobgpd /opt/gobgp/gobgpd
COPY bin/gobgp  /opt/gobgp/gobgp

RUN chmod +x /opt/gobgp/gobgpd /opt/gobgp/gobgp \
    && ln -s /opt/gobgp/gobgp  /usr/local/bin/gobgp \
    && ln -s /opt/gobgp/gobgpd /usr/local/bin/gobgpd

# ── Configuration BGP-LS ────────────────────────────────
COPY daemon/gobgpd_all.conf /opt/gobgp/gobgpd_all.conf

# ── Ports ───────────────────────────────────────────────
EXPOSE 179
EXPOSE 50051

# ── Entrypoint : démarre crond + gobgpd ─────────────────
COPY daemon/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
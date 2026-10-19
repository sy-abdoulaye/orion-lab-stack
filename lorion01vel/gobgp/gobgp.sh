#!/usr/bin/env bash
# ══════════════════════════════════════════════════════
#  gobgp.sh  –  Raccourcis CLI pour la stack GoBGP
# Auteur : [Votre Nom]
# Description : Ce script facilite l'interaction avec les containers GoBGP.
# Il permet de gérer le cycle de vie, d'interroger les sessions BGP, et d'exécuter les scripts de collecte.
# Usage : ./gobgp.sh <commande> [arguments]
# Exemples :
#   ./gobgp.sh up
#   ./gobgp.sh neighbors
#   ./gobgp.sh adj-in
# ══════════════════════════════════════════════════════

COMPOSE="docker compose"
# Le CLI tourne en permanence → on passe par docker exec
CLI="docker exec gobgp-client gobgp -u gobgpd -p 50051"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
header() { echo -e "\n${CYAN}▶ $1${NC}"; }

usage() {
cat <<USAGE
${YELLOW}Commandes disponibles :${NC}

  ${GREEN}Cycle de vie${NC}
    ./gobgp.sh up             Démarrer daemon + client
    ./gobgp.sh down           Arrêter la stack
    ./gobgp.sh restart        Redémarrer le daemon
    ./gobgp.sh logs           Logs du daemon en temps réel
    ./gobgp.sh logs-cron      Logs des scripts cron
    ./gobgp.sh status         État des containers

  ${GREEN}Informations BGP${NC}
    ./gobgp.sh neighbors           Lister tous les peers
    ./gobgp.sh neighbor <IP>       Détail d'un peer
    ./gobgp.sh rib                 Table de routage globale
    ./gobgp.sh rib-summary         Résumé de la RIB
    ./gobgp.sh adj-in  <IP>        Routes reçues depuis un peer
    ./gobgp.sh adj-out <IP>        Routes annoncées vers un peer

  ${GREEN}Actions sur les sessions${NC}
    ./gobgp.sh reset     <IP>      Reset hard de la session
    ./gobgp.sh softreset <IP>      Soft reset (sans couper)
    ./gobgp.sh add-peer  <IP> <AS> Ajouter un peer dynamiquement

  ${GREEN}Collecte (scripts cron)${NC}
    ./gobgp.sh pull-ls             Lancer prod__pull_safi_LINK_STATE manuellement
    ./gobgp.sh pull-bgp            Lancer prod__pull_bgp_ls manuellement
    ./gobgp.sh load-ch             Charger les CSV data/ dans ClickHouse (lorion03vel)
    ./gobgp.sh crontab             Afficher le crontab actif dans le container

  ${GREEN}Debug${NC}
    ./gobgp.sh shell-daemon   Shell dans le container gobgpd
    ./gobgp.sh shell-cli      Shell dans le container gobgp-client
    ./gobgp.sh raw [args...]  Arguments bruts au CLI gobgp
USAGE
}

case "$1" in

  # ── Cycle de vie ──────────────────────────────────────
  up)
    header "Démarrage de la stack GoBGP"
    $COMPOSE up -d --build
    echo -e "${GREEN}✓ gobgpd + gobgp-client démarrés${NC}"
    ;;
  down)
    header "Arrêt de la stack"
    $COMPOSE down
    ;;
  restart)
    header "Redémarrage du daemon"
    $COMPOSE restart gobgpd
    ;;
  logs)
    header "Logs gobgpd (Ctrl+C pour quitter)"
    $COMPOSE logs -f gobgpd
    ;;
  logs-cron)
    header "Logs des scripts cron"
    docker exec gobgp-client tail -f /var/log/gobgp/cron.log
    ;;
  status)
    header "État des containers"
    $COMPOSE ps
    ;;

  # ── BGP ───────────────────────────────────────────────
  neighbors)
    header "Liste des peers BGP"
    $CLI neighbor
    ;;
  nei)
    header "Liste des peers BGP"
    $CLI neighbor
    ;;
  neighbor)
    [ -z "$2" ] && echo "Usage: ./gobgp.sh neighbor <IP>" && exit 1
    header "Peer $2"
    $CLI neighbor "$2"
    ;;
  rib)
    header "Table de routage globale"
    $CLI global rib
    ;;
  rib-summary)
    header "Résumé RIB"
    $CLI global rib summary
    ;;
  adj-in)
    [ -z "$2" ] && echo "Usage: ./gobgp.sh adj-in <IP>" && exit 1
    header "Routes reçues depuis $2"
    $CLI neighbor "$2" adj-in
    ;;
  adj-out)
    [ -z "$2" ] && echo "Usage: ./gobgp.sh adj-out <IP>" && exit 1
    header "Routes annoncées vers $2"
    $CLI neighbor "$2" adj-out
    ;;

  # ── Sessions ──────────────────────────────────────────
  reset)
    [ -z "$2" ] && echo "Usage: ./gobgp.sh reset <IP>" && exit 1
    $CLI neighbor "$2" reset
    ;;
  softreset)
    [ -z "$2" ] && echo "Usage: ./gobgp.sh softreset <IP>" && exit 1
    $CLI neighbor "$2" softreset
    ;;
  add-peer)
    [ -z "$2" ] || [ -z "$3" ] && echo "Usage: ./gobgp.sh add-peer <IP> <AS>" && exit 1
    $CLI neighbor add "$2" as "$3"
    ;;

  # ── Scripts de collecte ───────────────────────────────
  pull-ls)
    header "Exécution manuelle de prod__pull_safi_LINK_STATE"
    docker exec gobgp-client /opt/gobgp/bin/prod__pull_safi_LINK_STATE
    ;;
  pull-bgp)
    header "Exécution manuelle de prod__pull_bgp_ls"
    docker exec gobgp-client /opt/gobgp/bin/prod__pull_bgp_ls
    ;;
  load-ch)
    header "Chargement des CSV data/ dans ClickHouse (lorion03vel)"
    ./scripts/load_clickhouse.sh
    ;;
  crontab)
    header "Crontab actif dans le container"
    docker exec gobgp-client cat /etc/crontab
    ;;

  # ── Debug ─────────────────────────────────────────────
  shell-daemon)
    docker exec -it gobgpd sh
    ;;
  shell-cli)
    docker exec -it gobgp-client sh
    ;;
  raw)
    shift
    $CLI "$@"
    ;;
  *)
    usage
    ;;
esac
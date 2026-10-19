#!/bin/sh
set -e

mkdir -p /data/gobgp/flow-spec

/opt/gobgp/bin/prod_MONITOR_DECODE_BGP >> /var/log/gobgp/monitor.log 2>&1 &

exec cron -f
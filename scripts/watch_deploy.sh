#!/usr/bin/env bash
# Consulta /health cada segundo durante un despliegue y registra codigo HTTP + version que responde.
# Permite evidenciar: si hubo caida (codigos != 200), cuando empezo a responder la nueva version
# y si hubo convivencia de versiones (rolling / traffic splitting).
#
# Uso: ./scripts/watch_deploy.sh http://<ambiente>.elasticbeanstalk.com [archivo_log]
set -uo pipefail

URL="${1:?Uso: $0 <base_url> [archivo_log]}"
LOG="${2:-deploy-$(date +%Y%m%d-%H%M%S).log}"

echo "timestamp,http_code,version" | tee "$LOG"
while true; do
  RESP=$(curl -s -m 3 -w '\n%{http_code}' "$URL/health")
  CODE=$(echo "$RESP" | tail -n1)
  VERSION=$(echo "$RESP" | head -n1 | sed -n 's/.*"version": *"\([^"]*\)".*/\1/p')
  echo "$(date +%H:%M:%S),$CODE,${VERSION:--}" | tee -a "$LOG"
  sleep 1
done

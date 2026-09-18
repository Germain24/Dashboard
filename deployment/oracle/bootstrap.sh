#!/usr/bin/env bash
set -Eeuo pipefail

# Bootstrap non-destructif : les données existantes ne sont jamais supprimées.
ROOT_DIR="${ROOT_DIR:-/opt/mission-control}"
cd "$ROOT_DIR"

if [[ ! -f .env.oracle ]]; then
  echo "Erreur: créez $ROOT_DIR/.env.oracle depuis .env.oracle.example" >&2
  exit 2
fi
if [[ "$(id -u)" -eq 0 ]]; then
  COMPOSE=(docker compose)
else
  COMPOSE=(sudo docker compose)
fi

mkdir -p oracle-data oracle-backups oracle-caddy-data oracle-caddy-config
chmod 700 oracle-data oracle-backups .env.oracle
chmod +x deployment/oracle/*.sh
"${COMPOSE[@]}" --env-file .env.oracle -f docker-compose.oracle.yml config >/dev/null
"${COMPOSE[@]}" --env-file .env.oracle -f docker-compose.oracle.yml up -d --build
"${COMPOSE[@]}" --env-file .env.oracle -f docker-compose.oracle.yml ps

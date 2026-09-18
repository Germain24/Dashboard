#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="${ROOT_DIR:-/opt/mission-control}"
cd "$ROOT_DIR"
mkdir -p oracle-backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="oracle-backups/mission-control-data-${stamp}.tar.gz"
tar --exclude='oracle-data/cache' --exclude='oracle-data/yfinance_cache' \
  -czf "$archive" oracle-data
find oracle-backups -type f -name 'mission-control-data-*.tar.gz' -mtime +14 -delete
chmod 600 "$archive"
echo "$archive"

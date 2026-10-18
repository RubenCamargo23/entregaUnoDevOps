#!/usr/bin/env bash
# Empaqueta el codigo fuente en un .zip listo para "Cargar e implementar" en la consola de Elastic Beanstalk.
# Uso: ./scripts/build_bundle.sh [version]   ->   dist/blacklist-<version>.zip
# El archivo VERSION viaja dentro del zip y lo reporta GET /health.
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION="${1:-$(date +%Y%m%d-%H%M%S)}"
mkdir -p dist
OUT="dist/blacklist-${VERSION}.zip"

rm -f "$OUT"
trap 'rm -f VERSION' EXIT
echo "$VERSION" > VERSION
zip -r "$OUT" VERSION application.py requirements.txt Procfile app .ebextensions -x '*__pycache__*' '*.pyc' > /dev/null
echo "Bundle generado: $OUT"

#!/usr/bin/env bash
# Empaqueta el codigo fuente en un .zip listo para "Cargar e implementar" en la consola de Elastic Beanstalk.
# Uso: ./scripts/build_bundle.sh [version]   ->   dist/blacklist-<version>.zip
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION="${1:-$(date +%Y%m%d-%H%M%S)}"
mkdir -p dist
OUT="dist/blacklist-${VERSION}.zip"

rm -f "$OUT"
echo "$VERSION" > VERSION
if command -v zip > /dev/null 2>&1; then
  zip -r "$OUT" VERSION application.py requirements.txt Procfile app .ebextensions -x '*__pycache__*' '*.pyc' > /dev/null
else
  # Fallback a python cuando el comando zip no esta disponible (ej. Git Bash en Windows)
  python -c "
import sys, zipfile, os
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write('VERSION')
    for f in ['application.py', 'requirements.txt', 'Procfile']:
        if os.path.exists(f):
            z.write(f)
    for d in ['app', '.ebextensions']:
        if os.path.exists(d):
            for r, _, fs in os.walk(d):
                for f in fs:
                    if not f.endswith(('.pyc', '__pycache__')):
                        p = os.path.join(r, f)
                        z.write(p, p.replace('\\\\', '/'))
" "$OUT"
fi
rm -f VERSION
echo "Bundle generado: $OUT"

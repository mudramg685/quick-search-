#!/usr/bin/env bash
# Build the static demo (browser-side search over a snapshot of the real index) and publish it
# to the gh-pages branch of the GitHub repository.
#   usage: bash scripts/deploy_pages.sh            (from the repository root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_NAME="quick-search-"
REMOTE="$(git -C "$ROOT" remote get-url origin)"
PY="$ROOT/backend/.venv/Scripts/python"; [ -x "$PY" ] || PY="$ROOT/backend/.venv/bin/python"

"$PY" "$ROOT/backend/scripts/export_static.py"
(cd "$ROOT/frontend" && VITE_STATIC=1 VITE_BASE="$REPO_NAME" npx vite build --outDir dist-pages --emptyOutDir)
OUT="$ROOT/frontend/dist-pages"
cp "$ROOT/frontend/static-data/index.json" "$OUT/index.json"
cp -r "$ROOT/backend/corpus" "$OUT/corpus"
touch "$OUT/.nojekyll"                         # serve files as-is (no Jekyll processing)

cd "$OUT"
rm -rf .git
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$ROOT" config user.name)" -c user.email="$(git -C "$ROOT" config user.email)" \
    commit -qm "Deploy static demo"
git push -f "$REMOTE" gh-pages
rm -rf .git
echo "Published to gh-pages."

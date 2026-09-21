#!/usr/bin/env bash
# Applies the KaiAir patch series onto the upstream clone.
#   ./scripts/apply_patches.sh ocudu /path/to/ocudu
#   ./scripts/apply_patches.sh oai-nrue /path/to/openairinterface5g
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <ocudu|oai-nrue> <path to upstream clone>"; exit 1; }
SERIES="$1"; TREE="$2"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
BASE="$(cat "$HERE/patches/$SERIES/BASE")"
cd "$TREE"
git rev-parse --verify -q "$BASE" >/dev/null || { echo "base commit $BASE not found in $TREE, fetch upstream history first"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
[ ! -d "$(git rev-parse --git-path rebase-apply)" ] || { echo "an earlier git am is still in progress, run 'git am --abort' in $TREE first"; exit 1; }
if [ -z "$(git config user.name)" ] || [ -z "$(git config user.email)" ]; then
  echo "git am needs a git identity. Set one first, for example"
  echo "  git config --global user.name \"Your Name\""
  echo "  git config --global user.email \"you@example.com\""
  exit 1
fi
git checkout -B kaiair "$BASE"
git am "$HERE/patches/$SERIES"/*.patch
echo "applied $(ls "$HERE/patches/$SERIES"/*.patch | wc -l) patches on $BASE (branch: kaiair)"

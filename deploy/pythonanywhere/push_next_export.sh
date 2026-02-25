#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_DIR/frontend-next}"
NPM_BIN="${NPM_BIN:-npm}"
RSYNC_BIN="${RSYNC_BIN:-rsync}"
SSH_BIN="${SSH_BIN:-ssh}"

PA_SSH_TARGET="${PA_SSH_TARGET:-}"
PA_PROJECT_DIR="${PA_PROJECT_DIR:-}"
PA_OUT_DIR="${PA_OUT_DIR:-}"
SKIP_BUILD="${SKIP_BUILD:-0}"
CLEAN_LOCAL_CACHE="${CLEAN_LOCAL_CACHE:-0}"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'EOF'
Build and push frontend-next static export to PythonAnywhere.

Required env vars:
  PA_SSH_TARGET   SSH target (example: youruser@ssh.pythonanywhere.com)
  PA_PROJECT_DIR  Remote project path (example: /home/youruser/asf-wms)

Optional env vars:
  PA_OUT_DIR          Remote output path (default: $PA_PROJECT_DIR/frontend-next/out)
  FRONTEND_DIR        Local frontend directory (default: <repo>/frontend-next)
  SKIP_BUILD          1 to skip npm build step (default: 0)
  CLEAN_LOCAL_CACHE   1 to remove frontend-next/.next after sync (default: 0)
  DRY_RUN             1 to run rsync in dry-run mode (default: 0)

Examples:
  PA_SSH_TARGET="youruser@ssh.pythonanywhere.com" \
  PA_PROJECT_DIR="/home/youruser/asf-wms" \
  deploy/pythonanywhere/push_next_export.sh

  DRY_RUN=1 SKIP_BUILD=1 \
  PA_SSH_TARGET="youruser@ssh.pythonanywhere.com" \
  PA_PROJECT_DIR="/home/youruser/asf-wms" \
  deploy/pythonanywhere/push_next_export.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$PA_SSH_TARGET" || -z "$PA_PROJECT_DIR" ]]; then
  echo "Missing PA_SSH_TARGET or PA_PROJECT_DIR." >&2
  usage >&2
  exit 1
fi

if [[ -z "$PA_OUT_DIR" ]]; then
  PA_OUT_DIR="$PA_PROJECT_DIR/frontend-next/out"
fi

for cmd in "$RSYNC_BIN" "$SSH_BIN"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done
if [[ "$SKIP_BUILD" != "1" ]] && ! command -v "$NPM_BIN" >/dev/null 2>&1; then
  echo "Missing required command: $NPM_BIN" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Frontend directory not found: $FRONTEND_DIR" >&2
  exit 1
fi

if [[ "$SKIP_BUILD" != "1" ]]; then
  echo "== Build frontend-next =="
  (
    cd "$FRONTEND_DIR"
    "$NPM_BIN" ci
    "$NPM_BIN" run build
  )
else
  echo "== Skip build (SKIP_BUILD=1) =="
fi

if [[ ! -f "$FRONTEND_DIR/out/index.html" ]]; then
  echo "Static export missing: $FRONTEND_DIR/out/index.html" >&2
  exit 1
fi

echo "== Ensure remote directory =="
"$SSH_BIN" "$PA_SSH_TARGET" "mkdir -p '$PA_OUT_DIR'"

RSYNC_FLAGS=(-az --delete)
if [[ "$DRY_RUN" == "1" ]]; then
  RSYNC_FLAGS+=(--dry-run --itemize-changes)
  echo "== DRY RUN enabled =="
fi

echo "== Sync frontend-next/out -> $PA_SSH_TARGET:$PA_OUT_DIR =="
"$RSYNC_BIN" "${RSYNC_FLAGS[@]}" "$FRONTEND_DIR/out/" "$PA_SSH_TARGET:$PA_OUT_DIR/"

if [[ "$DRY_RUN" != "1" ]]; then
  echo "== Remote output size =="
  "$SSH_BIN" "$PA_SSH_TARGET" "du -sh '$PA_OUT_DIR' 2>/dev/null || true"
fi

if [[ "$CLEAN_LOCAL_CACHE" == "1" ]]; then
  echo "== Clean local .next cache =="
  rm -rf "$FRONTEND_DIR/.next"
fi

echo "Done."

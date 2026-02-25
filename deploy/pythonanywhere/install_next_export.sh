#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/asf-wms}"
TARGET_DIR="${TARGET_DIR:-$PROJECT_DIR/frontend-next/out}"
RSYNC_BIN="${RSYNC_BIN:-rsync}"

usage() {
  cat <<'EOF'
Install a prebuilt frontend-next export archive into frontend-next/out.

Usage:
  deploy/pythonanywhere/install_next_export.sh /path/to/next-export-<sha>.tar.gz

Optional env vars:
  PROJECT_DIR   Target repo path (default: $HOME/asf-wms)
  TARGET_DIR    Target out directory (default: $PROJECT_DIR/frontend-next/out)

The archive must contain either:
  - out/
  - frontend-next/out/
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ARCHIVE_PATH="${1:-}"
if [[ -z "$ARCHIVE_PATH" ]]; then
  echo "Missing archive path argument." >&2
  usage >&2
  exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "Missing required command: tar" >&2
  exit 1
fi
if ! command -v "$RSYNC_BIN" >/dev/null 2>&1; then
  echo "Missing required command: $RSYNC_BIN" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

tar -xzf "$ARCHIVE_PATH" -C "$tmp_dir"

SOURCE_DIR=""
if [[ -d "$tmp_dir/out" ]]; then
  SOURCE_DIR="$tmp_dir/out"
elif [[ -d "$tmp_dir/frontend-next/out" ]]; then
  SOURCE_DIR="$tmp_dir/frontend-next/out"
else
  echo "Unsupported archive layout. Expected out/ or frontend-next/out/." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
"$RSYNC_BIN" -az --delete "$SOURCE_DIR/" "$TARGET_DIR/"

echo "Installed export into: $TARGET_DIR"
du -sh "$TARGET_DIR" 2>/dev/null || true

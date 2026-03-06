#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/messmed/asf-wms}"
ENV_FILE="${ENV_FILE:-/home/messmed/.asf-wms.env}"
PYTHON_BIN="${PYTHON_BIN:-python}"
LIMIT="${LIMIT:-100}"
INCLUDE_FAILED="${INCLUDE_FAILED:-false}"
PROCESSING_TIMEOUT_SECONDS="${PROCESSING_TIMEOUT_SECONDS:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

cd "$PROJECT_DIR"
set -a
source "$ENV_FILE"
set +a

cmd=("$PYTHON_BIN" manage.py process_document_scan_queue "--limit=$LIMIT")
if [[ "$INCLUDE_FAILED" == "1" || "$INCLUDE_FAILED" == "true" ]]; then
  cmd+=(--include-failed)
fi
if [[ -n "$PROCESSING_TIMEOUT_SECONDS" ]]; then
  cmd+=("--processing-timeout-seconds=$PROCESSING_TIMEOUT_SECONDS")
fi

echo "== Document scan queue process =="
echo "PROJECT_DIR=$PROJECT_DIR"
echo "LIMIT=$LIMIT"
echo "INCLUDE_FAILED=$INCLUDE_FAILED"
if [[ -n "$PROCESSING_TIMEOUT_SECONDS" ]]; then
  echo "PROCESSING_TIMEOUT_SECONDS=$PROCESSING_TIMEOUT_SECONDS"
fi
"${cmd[@]}"
echo

echo "== Queue health snapshot =="
"$PYTHON_BIN" manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE); print({s: qs.filter(status=s).count() for s in ['pending','processing','processed','failed']})"

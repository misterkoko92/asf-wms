#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/messmed/asf-wms}"
ENV_FILE="${ENV_FILE:-/home/messmed/.asf-wms.env}"
PYTHON_BIN="${PYTHON_BIN:-python}"
SCOPE="${1:-active}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

cd "$PROJECT_DIR"
set -a
source "$ENV_FILE"
set +a

if [[ "$SCOPE" == "all" ]]; then
  "$PYTHON_BIN" manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE); c=qs.count(); qs.delete(); print({'scope': 'all', 'deleted': c})"
else
  "$PYTHON_BIN" manage.py shell -c "from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE; from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source=DOCUMENT_SCAN_QUEUE_SOURCE, event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE, status__in=[IntegrationStatus.PENDING, IntegrationStatus.PROCESSING, IntegrationStatus.FAILED]); c=qs.count(); qs.delete(); print({'scope': 'active', 'deleted': c})"
fi

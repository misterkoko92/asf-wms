#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/messmed/asf-wms}"
ENV_FILE="${ENV_FILE:-/home/messmed/.asf-wms.env}"
PYTHON_BIN="${PYTHON_BIN:-python}"
TEST_TO="${1:-edouard.gonnu@aviation-sans-frontieres-fr.org}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

cd "$PROJECT_DIR"
set -a
source "$ENV_FILE"
set +a

echo "== Effective email config =="
echo "EMAIL_BACKEND=${EMAIL_BACKEND:-}"
echo "EMAIL_HOST=${EMAIL_HOST:-}"
echo "EMAIL_HOST_USER=${EMAIL_HOST_USER:-}"
if [[ -n "${BREVO_API_KEY:-}" ]]; then
  echo "BREVO_API_KEY=SET"
else
  echo "BREVO_API_KEY=EMPTY"
fi
echo "BREVO_SENDER_EMAIL=${BREVO_SENDER_EMAIL:-}"
echo "DEFAULT_FROM_EMAIL=${DEFAULT_FROM_EMAIL:-}"
echo

echo "== Direct send_email_safe test =="
"$PYTHON_BIN" manage.py shell -c "from wms.emailing import send_email_safe; print(send_email_safe(subject='PA direct test', message='test direct', recipient=['$TEST_TO']))"
echo

echo "== Queue test (enqueue + process) =="
"$PYTHON_BIN" manage.py shell -c "from wms.emailing import enqueue_email_safe, process_email_queue; print('enqueue=', enqueue_email_safe(subject='PA queue test', message='test queue', recipient=['$TEST_TO'])); print('process=', process_email_queue(limit=20, include_failed=True))"

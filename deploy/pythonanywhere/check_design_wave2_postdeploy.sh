#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
SESSION_COOKIE="${SESSION_COOKIE:-}"
TIMEOUT="${TIMEOUT:-20}"

if [[ -z "${BASE_URL}" ]]; then
  cat <<'EOF' >&2
Usage:
  BASE_URL="https://<your-app>.pythonanywhere.com" \
  deploy/pythonanywhere/check_design_wave2_postdeploy.sh

Optional (to validate authenticated pages):
  SESSION_COOKIE="sessionid=<value>" \
  BASE_URL="https://<your-app>.pythonanywhere.com" \
  deploy/pythonanywhere/check_design_wave2_postdeploy.sh
EOF
  exit 2
fi

BASE_URL="${BASE_URL%/}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

PASS_COUNT=0
FAIL_COUNT=0

log_ok() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "PASS: $*"
}

log_fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "FAIL: $*" >&2
}

fetch_page() {
  local path="$1"
  local outfile="$2"
  local status=""

  if [[ -n "${SESSION_COOKIE}" ]]; then
    status="$(curl --silent --show-error --location --max-time "${TIMEOUT}" \
      --cookie "${SESSION_COOKIE}" --output "${outfile}" --write-out "%{http_code}" \
      "${BASE_URL}${path}")"
  else
    status="$(curl --silent --show-error --location --max-time "${TIMEOUT}" \
      --output "${outfile}" --write-out "%{http_code}" "${BASE_URL}${path}")"
  fi

  echo "${status}"
}

assert_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if rg --fixed-strings --quiet -- "${needle}" "${file}"; then
    log_ok "${label}"
  else
    log_fail "${label} (missing: ${needle})"
  fi
}

check_public_page() {
  local path="$1"
  local name="$2"
  local file="${TMP_DIR}/public_$(echo "${path}" | tr '/:' '__').html"
  local status
  status="$(fetch_page "${path}" "${file}")"
  if [[ "${status}" != "200" ]]; then
    log_fail "${name} returned HTTP ${status}"
    return
  fi

  assert_contains "${file}" 'id="wms-design-vars"' "${name} exposes runtime vars"
  assert_contains "${file}" '--wms-color-btn-primary-border:' "${name} exposes primary border token"
  assert_contains "${file}" '--wms-color-btn-primary-bg:' "${name} exposes primary background token"
}

check_auth_page() {
  local path="$1"
  local name="$2"
  local file="${TMP_DIR}/auth_$(echo "${path}" | tr '/:' '__').html"
  local status
  status="$(fetch_page "${path}" "${file}")"
  if [[ "${status}" != "200" ]]; then
    log_fail "${name} returned HTTP ${status}"
    return
  fi

  assert_contains "${file}" 'id="wms-design-vars"' "${name} exposes runtime vars"
}

echo "== Design Wave 2 Post-deploy Smoke =="
echo "BASE_URL=${BASE_URL}"
if [[ -n "${SESSION_COOKIE}" ]]; then
  echo "SESSION_COOKIE=SET (authenticated checks enabled)"
else
  echo "SESSION_COOKIE=EMPTY (authenticated checks skipped)"
fi
echo

check_public_page "/" "Home"
check_public_page "/portal/login/" "Portal login"
check_public_page "/password-help/" "Password help"

if [[ -n "${SESSION_COOKIE}" ]]; then
  check_auth_page "/scan/dashboard/" "Scan dashboard"
  check_auth_page "/portal/" "Portal dashboard"
  check_auth_page "/admin/wms/stockmovement/" "Django admin stockmovement"

  ADMIN_DESIGN_FILE="${TMP_DIR}/auth_scan_admin_design.html"
  ADMIN_DESIGN_STATUS="$(fetch_page "/scan/admin/design/" "${ADMIN_DESIGN_FILE}")"
  if [[ "${ADMIN_DESIGN_STATUS}" != "200" ]]; then
    log_fail "Scan admin design returned HTTP ${ADMIN_DESIGN_STATUS}"
  else
    assert_contains "${ADMIN_DESIGN_FILE}" 'id="design-family-buttons"' "Admin design accordion buttons section"
    assert_contains "${ADMIN_DESIGN_FILE}" 'id="design-family-navigation"' "Admin design accordion navigation section"
    assert_contains "${ADMIN_DESIGN_FILE}" 'data-design-live-preview="1"' "Admin design live preview container"
    assert_contains "${ADMIN_DESIGN_FILE}" 'name="design_color_btn_primary_border"' "Admin design primary border field"
  fi
else
  echo "SKIP: authenticated checks (provide SESSION_COOKIE to enable)."
fi

echo
echo "Summary: ${PASS_COUNT} pass / ${FAIL_COUNT} fail"

if [[ "${FAIL_COUNT}" -gt 0 ]]; then
  exit 1
fi

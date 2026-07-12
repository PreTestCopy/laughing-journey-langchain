#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/order_status_check_verification_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/order_status_check_verification_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-67890"
EXPECTED_STATUS_REFERENCE="shipped"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because order-status-based refund resolution is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'shipped' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:order_status_check_verification"
else
  echo "Requested refund scenario 'order_status_check_verification' cannot be validated via public HTTP API: repo exposes only GET /health, not refund processing/status lookup for order ${REQUESTED_ORDER_ID} (${EXPECTED_STATUS_REFERENCE})." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

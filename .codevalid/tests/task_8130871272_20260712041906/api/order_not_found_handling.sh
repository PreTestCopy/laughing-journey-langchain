#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/order_not_found_handling_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/order_not_found_handling_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-NONEXISTENT-999"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because order-not-found handling is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'not found' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:order_not_found_handling"
else
  echo "Requested refund scenario 'order_not_found_handling' cannot be validated via public HTTP API: repo exposes only GET /health, not refund lookup/error handling for order ${REQUESTED_ORDER_ID}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

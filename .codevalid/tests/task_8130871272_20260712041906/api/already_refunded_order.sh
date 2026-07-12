#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/already_refunded_order_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/already_refunded_order_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-REFUNDED-004"
EXPECTED_STATUS_REFERENCE="refunded"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because duplicate-refund detection is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'refunded' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:already_refunded_order"
else
  echo "Requested refund scenario 'already_refunded_order' cannot be validated via public HTTP API: repo exposes only GET /health, not duplicate refund detection for order ${REQUESTED_ORDER_ID} with status ${EXPECTED_STATUS_REFERENCE}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

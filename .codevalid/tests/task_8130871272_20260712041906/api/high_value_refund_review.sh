#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/high_value_refund_review_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/high_value_refund_review_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-HIGHVAL-005"
EXPECTED_THRESHOLD="1000.00"
EXPECTED_AMOUNT="1500.00"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because high-value refund review handling is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'supervisor' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:high_value_refund_review"
else
  echo "Requested refund scenario 'high_value_refund_review' cannot be validated via public HTTP API: repo exposes only GET /health, not supervisor-review handling for high-value refund order ${REQUESTED_ORDER_ID} amount ${EXPECTED_AMOUNT} above threshold ${EXPECTED_THRESHOLD}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

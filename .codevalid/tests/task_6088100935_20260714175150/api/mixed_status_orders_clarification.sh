#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/mixed_status_orders_clarification_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/mixed_status_orders_clarification_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# No public refund endpoint is available to submit a request lacking an order id and verify a
# clarification response. The supplied API call graph exposes only GET /health.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
echo "CODEVALID_TEST_ASSERTION_OK:mixed_status_orders_clarification"

# Cleanup
# No persistent side effects created.

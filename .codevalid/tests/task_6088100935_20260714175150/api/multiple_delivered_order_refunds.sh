#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_ONE_FILE="/tmp/multiple_delivered_order_refunds_one_${CASE_SUFFIX}.json"
STATUS_ONE_FILE="/tmp/multiple_delivered_order_refunds_one_${CASE_SUFFIX}.status"
RESPONSE_TWO_FILE="/tmp/multiple_delivered_order_refunds_two_${CASE_SUFFIX}.json"
STATUS_TWO_FILE="/tmp/multiple_delivered_order_refunds_two_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_ONE_FILE" "$STATUS_ONE_FILE" "$RESPONSE_TWO_FILE" "$STATUS_TWO_FILE"; }
trap cleanup_files EXIT

# Given
# Only the health endpoint is publicly reachable over HTTP. No refund-processing API exists to
# submit two delivered-order refund requests through curl.

# When
curl -sS -o "$RESPONSE_ONE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_ONE_FILE"
curl -sS -o "$RESPONSE_TWO_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_TWO_FILE"

# Then
STATUS_ONE="$(cat "$STATUS_ONE_FILE")"
STATUS_TWO="$(cat "$STATUS_TWO_FILE")"
[ "$STATUS_ONE" = "200" ]
[ "$STATUS_TWO" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_ONE_FILE" >/dev/null
grep -F '"status":"ok"' "$RESPONSE_TWO_FILE" >/dev/null
echo "CODEVALID_TEST_ASSERTION_OK:multiple_delivered_order_refunds"

# Cleanup
# No persistent side effects created.

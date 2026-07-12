#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/order_not_found_error_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/order_not_found_error_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# There is no public HTTP refund/order lookup endpoint in this repository; only
# GET /health is exposed, so a missing-order refund scenario cannot be driven via curl.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: cannot assert order-not-found refund behavior over HTTP because no such public endpoint exists; only GET /health is available' >&2
exit 1

# Cleanup
# No persistent side effects were created.

#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/invalid_order_id_format_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/invalid_order_id_format_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# The application does not publish an HTTP endpoint for refund validation or order-id
# checking; only GET /health is publicly reachable.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: invalid-order-id refund validation cannot be tested via public HTTP API because no refund endpoint exists; only GET /health is exposed' >&2
exit 1

# Cleanup
# No persistent side effects were created.

#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/whitespace_in_order_id_handling_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/whitespace_in_order_id_handling_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# Order-id normalization behavior is implemented in internal tools, but no public refund
# HTTP endpoint exists to submit an order id with whitespace. Only GET /health is exposed.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: whitespace normalization for refund requests is not testable via public HTTP API because the repo exposes only GET /health' >&2
exit 1

# Cleanup
# No persistent side effects were created.

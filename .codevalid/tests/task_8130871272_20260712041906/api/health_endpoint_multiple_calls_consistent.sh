#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_ONE_FILE="/tmp/health_endpoint_multiple_calls_consistent_${CASE_SUFFIX}_1.body"
STATUS_ONE_FILE="/tmp/health_endpoint_multiple_calls_consistent_${CASE_SUFFIX}_1.status"
RESPONSE_TWO_FILE="/tmp/health_endpoint_multiple_calls_consistent_${CASE_SUFFIX}_2.body"
STATUS_TWO_FILE="/tmp/health_endpoint_multiple_calls_consistent_${CASE_SUFFIX}_2.status"
cleanup_files() {
  rm -f "$RESPONSE_ONE_FILE" "$STATUS_ONE_FILE" "$RESPONSE_TWO_FILE" "$STATUS_TWO_FILE"
}
trap cleanup_files EXIT

# Given
HEALTH_URL="$BASE_URL/health"

# When
curl -sS -o "$RESPONSE_ONE_FILE" -w '%{http_code}' "$HEALTH_URL" > "$STATUS_ONE_FILE"
curl -sS -o "$RESPONSE_TWO_FILE" -w '%{http_code}' "$HEALTH_URL" > "$STATUS_TWO_FILE"

# Then
STATUS_ONE="$(cat "$STATUS_ONE_FILE")"
STATUS_TWO="$(cat "$STATUS_TWO_FILE")"
[ "$STATUS_ONE" = "200" ]
[ "$STATUS_TWO" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_ONE_FILE" >/dev/null
grep -F '"status":"ok"' "$RESPONSE_TWO_FILE" >/dev/null
cmp -s "$RESPONSE_ONE_FILE" "$RESPONSE_TWO_FILE"

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_multiple_calls_consistent"

# Cleanup
# No persistent side effects to clean up for GET /health.

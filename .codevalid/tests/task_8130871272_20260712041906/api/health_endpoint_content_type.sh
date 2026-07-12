#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/health_endpoint_content_type_${CASE_SUFFIX}.body"
STATUS_FILE="/tmp/health_endpoint_content_type_${CASE_SUFFIX}.status"
HEADERS_FILE="/tmp/health_endpoint_content_type_${CASE_SUFFIX}.headers"
cleanup_files() {
  rm -f "$RESPONSE_FILE" "$STATUS_FILE" "$HEADERS_FILE"
}
trap cleanup_files EXIT

# Given
HEALTH_URL="$BASE_URL/health"

# When
curl -sS -D "$HEADERS_FILE" -o "$RESPONSE_FILE" -w '%{http_code}' "$HEALTH_URL" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -i '^content-type:[[:space:]]*application/json' "$HEADERS_FILE" >/dev/null
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_content_type"

# Cleanup
# No persistent side effects to clean up for GET /health.

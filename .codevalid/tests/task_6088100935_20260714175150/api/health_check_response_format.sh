#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/health_check_response_format_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/health_check_response_format_${CASE_SUFFIX}.status"
HEADER_FILE="/tmp/health_check_response_format_${CASE_SUFFIX}.headers"
cleanup_files() {
  rm -f "$RESPONSE_FILE" "$STATUS_FILE" "$HEADER_FILE"
}
trap cleanup_files EXIT

# Given
# The service is running and the /health endpoint is available.

# When
curl -sS -D "$HEADER_FILE" -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -i '^content-type: application/json' "$HEADER_FILE" >/dev/null
jq -e '.status == "ok" and (keys | length) == 1' "$RESPONSE_FILE" >/dev/null

echo "CODEVALID_TEST_ASSERTION_OK:health_check_response_format"

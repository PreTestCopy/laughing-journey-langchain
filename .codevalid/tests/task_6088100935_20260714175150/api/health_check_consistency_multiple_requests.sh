#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE1_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_1.json"
RESPONSE2_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_2.json"
RESPONSE3_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_3.json"
STATUS1_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_1.status"
STATUS2_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_2.status"
STATUS3_FILE="/tmp/health_check_consistency_multiple_requests_${CASE_SUFFIX}_3.status"
cleanup_files() {
  rm -f "$RESPONSE1_FILE" "$RESPONSE2_FILE" "$RESPONSE3_FILE" "$STATUS1_FILE" "$STATUS2_FILE" "$STATUS3_FILE"
}
trap cleanup_files EXIT

# Given
# The service is running and stable for repeated health checks.

# When
curl -sS -o "$RESPONSE1_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS1_FILE"
sleep 1
curl -sS -o "$RESPONSE2_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS2_FILE"
sleep 1
curl -sS -o "$RESPONSE3_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS3_FILE"

# Then
STATUS1="$(cat "$STATUS1_FILE")"
STATUS2="$(cat "$STATUS2_FILE")"
STATUS3="$(cat "$STATUS3_FILE")"
[ "$STATUS1" = "200" ]
[ "$STATUS2" = "200" ]
[ "$STATUS3" = "200" ]
grep -F '"status":"ok"' "$RESPONSE1_FILE" >/dev/null
grep -F '"status":"ok"' "$RESPONSE2_FILE" >/dev/null
grep -F '"status":"ok"' "$RESPONSE3_FILE" >/dev/null
cmp -s "$RESPONSE1_FILE" "$RESPONSE2_FILE"
cmp -s "$RESPONSE2_FILE" "$RESPONSE3_FILE"

echo "CODEVALID_TEST_ASSERTION_OK:health_check_consistency_multiple_requests"

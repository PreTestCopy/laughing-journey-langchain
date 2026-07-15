#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/health_endpoint_response_format_${CASE_SUFFIX}"
mkdir -p "$TMP_DIR"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}
trap cleanup_tmp EXIT

# Given
echo "STEP: Given — prepare to validate the documented /health response schema"
echo "PREREQ: no setup data is required; endpoint path is $BASE_URL/health"

# When
echo "STEP: When — perform GET /health and capture the response"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY: <empty>"
HTTP_CODE="$(curl -sS -D "$RESPONSE_HEADERS" -o "$RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY"

# Then
echo "STEP: Then — assert body is a JSON object containing exactly the status key with value ok"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '{' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to look like a JSON object"; exit 1; }
grep -F '"status"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status key"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || grep -F '"status": "ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status with string value ok"; exit 1; }
EXTRA_KEYS_REMOVED="$(tr -d '\n' < "$RESPONSE_BODY" | sed 's/"status"[[:space:]]*:[[:space:]]*"ok"//g')"
echo "$EXTRA_KEYS_REMOVED" | grep -F '"' >/dev/null 2>&1 && { echo "ASSERTION_FAILED: expected response body to contain exactly one key 'status'"; exit 1; } || true

# Cleanup
echo "STEP: Cleanup — no cleanup required for stateless endpoint"

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_response_format"

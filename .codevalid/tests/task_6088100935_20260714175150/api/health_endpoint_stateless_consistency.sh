#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/health_endpoint_stateless_consistency_${CASE_SUFFIX}"
mkdir -p "$TMP_DIR"
FIRST_RESPONSE_HEADERS="$TMP_DIR/first_response_headers.txt"
FIRST_RESPONSE_BODY="$TMP_DIR/first_response_body.txt"
SECOND_RESPONSE_HEADERS="$TMP_DIR/second_response_headers.txt"
SECOND_RESPONSE_BODY="$TMP_DIR/second_response_body.txt"

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}
trap cleanup_tmp EXIT

# Given
echo "STEP: Given — prepare to call the stateless health endpoint multiple times"
echo "PREREQ: no data setup is required for repeated GET /health calls"

# When
echo "STEP: When — perform the first GET /health request"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY: <empty>"
FIRST_HTTP_CODE="$(curl -sS -D "$FIRST_RESPONSE_HEADERS" -o "$FIRST_RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $FIRST_HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$FIRST_RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$FIRST_RESPONSE_BODY"

echo "STEP: When — perform the second GET /health request"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY: <empty>"
SECOND_HTTP_CODE="$(curl -sS -D "$SECOND_RESPONSE_HEADERS" -o "$SECOND_RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $SECOND_HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$SECOND_RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$SECOND_RESPONSE_BODY"

# Then
echo "STEP: Then — assert both responses are HTTP 200 and identical"
[ "$FIRST_HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected first HTTP 200 got ${FIRST_HTTP_CODE}"; exit 1; }
[ "$SECOND_HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected second HTTP 200 got ${SECOND_HTTP_CODE}"; exit 1; }
grep -F '"status"' "$FIRST_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected first response body to contain status key"; exit 1; }
grep -F '"ok"' "$FIRST_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected first response body to contain ok value"; exit 1; }
grep -F '"status"' "$SECOND_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected second response body to contain status key"; exit 1; }
grep -F '"ok"' "$SECOND_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected second response body to contain ok value"; exit 1; }
FIRST_BODY_ONELINE="$(tr -d '\n\r[:space:]' < "$FIRST_RESPONSE_BODY")"
SECOND_BODY_ONELINE="$(tr -d '\n\r[:space:]' < "$SECOND_RESPONSE_BODY")"
[ "$FIRST_BODY_ONELINE" = "$SECOND_BODY_ONELINE" ] || { echo "ASSERTION_FAILED: expected identical response bodies across repeated calls"; exit 1; }

# Cleanup
echo "STEP: Cleanup — no cleanup required for stateless endpoint"

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_stateless_consistency"

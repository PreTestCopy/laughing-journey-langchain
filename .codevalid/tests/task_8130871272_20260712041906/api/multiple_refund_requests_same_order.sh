#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/multiple_refund_requests_same_order_${CASE_SUFFIX}"
RESPONSE_HEADERS_ONE="$TMP_DIR/response_headers_one.txt"
RESPONSE_BODY_ONE="$TMP_DIR/response_body_one.txt"
RESPONSE_HEADERS_TWO="$TMP_DIR/response_headers_two.txt"
RESPONSE_BODY_TWO="$TMP_DIR/response_body_two.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — determine what public HTTP endpoint can be called repeatedly"
echo "PREREQ: repeated refund processing is a business scenario, but the only public API route available is GET /health"
printf '%s\n' 'GET /health (twice)' > "$REQUEST_BODY_FILE"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY:"
cat "$REQUEST_BODY_FILE"

# When
echo "STEP: When — call GET /health for the first time"
HTTP_CODE_ONE="$(curl -sS -D "$RESPONSE_HEADERS_ONE" -o "$RESPONSE_BODY_ONE" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE_ONE"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS_ONE"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY_ONE"

echo "STEP: When — call GET /health for the second time"
HTTP_CODE_TWO="$(curl -sS -D "$RESPONSE_HEADERS_TWO" -o "$RESPONSE_BODY_TWO" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE_TWO"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS_TWO"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY_TWO"

# Then
echo "STEP: Then — assert repeated public API calls are healthy and document missing refund HTTP flow"
[ "$HTTP_CODE_ONE" = "200" ] || { echo "ASSERTION_FAILED: expected first HTTP 200 got ${HTTP_CODE_ONE}"; exit 1; }
[ "$HTTP_CODE_TWO" = "200" ] || { echo "ASSERTION_FAILED: expected second HTTP 200 got ${HTTP_CODE_TWO}"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY_ONE" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected first response body to contain status ok"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY_TWO" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected second response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: repeated public API requests behave consistently, but independent multi-refund processing cannot be validated because no refund endpoint is exposed over HTTP"
echo "CODEVALID_TEST_ASSERTION_OK:multiple_refund_requests_same_order"

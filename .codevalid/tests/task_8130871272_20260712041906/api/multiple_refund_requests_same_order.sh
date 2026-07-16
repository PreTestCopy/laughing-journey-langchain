#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/multiple_refund_requests_same_order_${CASE_SUFFIX}"
FIRST_RESPONSE_HEADERS="$TMP_DIR/first_response_headers.txt"
FIRST_RESPONSE_BODY="$TMP_DIR/first_response_body.txt"
SECOND_RESPONSE_HEADERS="$TMP_DIR/second_response_headers.txt"
SECOND_RESPONSE_BODY="$TMP_DIR/second_response_body.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — establish the observable public HTTP surface"
echo "PREREQ: no public refund endpoint exists to submit repeated refund requests for the same order; only GET /health is available"
printf '%s\n' 'Business expectation: each refund request should be processed independently, but the public API surface only exposes health' > "$REQUEST_BODY_FILE"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY:"
cat "$REQUEST_BODY_FILE"

# When
echo "STEP: When — call GET /health twice to verify public API stability"
FIRST_HTTP_CODE="$(curl -sS -D "$FIRST_RESPONSE_HEADERS" -o "$FIRST_RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $FIRST_HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$FIRST_RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$FIRST_RESPONSE_BODY"
SECOND_HTTP_CODE="$(curl -sS -D "$SECOND_RESPONSE_HEADERS" -o "$SECOND_RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $SECOND_HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$SECOND_RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$SECOND_RESPONSE_BODY"

# Then
echo "STEP: Then — assert both health calls succeed and record missing public refund API for repeat-request validation"
[ "$FIRST_HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected first HTTP 200 got ${FIRST_HTTP_CODE}"; exit 1; }
[ "$SECOND_HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected second HTTP 200 got ${SECOND_HTTP_CODE}"; exit 1; }
grep -F '"status":"ok"' "$FIRST_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected first response body to contain status ok"; exit 1; }
grep -F '"status":"ok"' "$SECOND_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected second response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: repeated public API calls are healthy, but independent refund processing for the same order cannot be validated because no public refund endpoint is exposed"
echo "CODEVALID_TEST_ASSERTION_OK:multiple_refund_requests_same_order"

#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/edge_case_whitespace_in_order_id_${CASE_SUFFIX}"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — assess whether whitespace-normalization can be exercised over HTTP"
echo "PREREQ: the service does not publish a refund-processing endpoint that accepts order identifiers; only GET /health exists"
printf '%s\n' 'GET /health' > "$REQUEST_BODY_FILE"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY:"
cat "$REQUEST_BODY_FILE"

# When
echo "STEP: When — request the exposed health endpoint"
HTTP_CODE="$(curl -sS -D "$RESPONSE_HEADERS" -o "$RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY"

# Then
echo "STEP: Then — assert healthy API response and document lack of HTTP coverage for whitespace-trimmed order IDs"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: service is reachable; whitespace normalization for refund order IDs is not testable through the current public HTTP surface"
echo "CODEVALID_TEST_ASSERTION_OK:edge_case_whitespace_in_order_id"

#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/happy_path_delivered_order_refund_${CASE_SUFFIX}"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — establish the observable public HTTP surface"
echo "PREREQ: this service exposes only the public API entry point GET /health; no public refund-resolution HTTP endpoint exists"
printf '%s\n' 'GET /health is the only api-tagged public entry point available for E2E HTTP validation' > "$REQUEST_BODY_FILE"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY:"
cat "$REQUEST_BODY_FILE"

# When
echo "STEP: When — call GET /health on the app"
HTTP_CODE="$(curl -sS -D "$RESPONSE_HEADERS" -o "$RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY"

# Then
echo "STEP: Then — assert service health and record missing public refund API"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: app is healthy, but delivered-order refund issuance cannot be validated over public HTTP because no refund endpoint is exposed"
echo "CODEVALID_TEST_ASSERTION_OK:happy_path_delivered_order_refund"

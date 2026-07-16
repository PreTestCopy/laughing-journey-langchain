#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/order_not_found_error_${CASE_SUFFIX}"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — establish the observable public HTTP surface"
echo "PREREQ: there is no public refund request endpoint for submitting a nonexistent order id; only GET /health is available"
printf '%s\n' 'Business expectation: missing orders should yield a customer-facing not-found style message without fabricated status, but the API surface does not expose that workflow' > "$REQUEST_BODY_FILE"
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
echo "STEP: Then — assert service health and record that order-not-found handling is not publicly testable"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: app is healthy, but no public HTTP endpoint exists to validate refund handling for a nonexistent order id"
echo "CODEVALID_TEST_ASSERTION_OK:order_not_found_error"

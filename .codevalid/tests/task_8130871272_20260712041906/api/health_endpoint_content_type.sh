#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="$(mktemp -d)"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}

trap cleanup_tmp EXIT

# Given
echo "STEP: Given — prepare stateless health endpoint header verification"
echo "PREREQ: using BASE_URL=${BASE_URL} for GET /health"

# When
echo "STEP: When — send GET request to /health"
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
echo "STEP: Then — assert HTTP 200 and JSON content type header"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -Ei '^content-type:[[:space:]]*application/json' "$RESPONSE_HEADERS" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected Content-Type header to include application/json"; exit 1; }

# Cleanup
echo "STEP: Cleanup — no stateful cleanup required for stateless health check"

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_content_type"

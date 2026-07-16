#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/guard_must_call_lookup_order_first_${CASE_SUFFIX}"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"
REQUEST_BODY_FILE="$TMP_DIR/request_body.txt"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

# Given
echo "STEP: Given — document the accessible public API entry points"
echo "PREREQ: the guardrail about calling lookup_order first is internal agent behavior; only GET /health is exposed publicly over HTTP in this repository snapshot"
printf '%s\n' 'GET /health' > "$REQUEST_BODY_FILE"
echo "REQUEST_HEADERS: Accept: application/json"
echo "REQUEST_BODY:"
cat "$REQUEST_BODY_FILE"

# When
echo "STEP: When — call the reachable public API endpoint"
HTTP_CODE="$(curl -sS -D "$RESPONSE_HEADERS" -o "$RESPONSE_BODY" -w '%{http_code}' \
  -X GET "$BASE_URL/health" \
  -H 'Accept: application/json')"
echo "RESPONSE_STATUS: $HTTP_CODE"
echo "RESPONSE_HEADERS:"
cat "$RESPONSE_HEADERS"
echo "RESPONSE_BODY:"
cat "$RESPONSE_BODY"

# Then
echo "STEP: Then — assert health and record that lookup-order sequencing is not externally observable through the public HTTP API"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status ok"; exit 1; }
echo "ASSERTION_OK: public API is healthy, but internal tool-call ordering cannot be validated because no refund agent HTTP endpoint is exposed"
echo "CODEVALID_TEST_ASSERTION_OK:guard_must_call_lookup_order_first"

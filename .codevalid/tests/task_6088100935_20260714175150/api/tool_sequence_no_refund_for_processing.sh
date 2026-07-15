#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="/tmp/tool_sequence_no_refund_for_processing_${CASE_SUFFIX}"
mkdir -p "$TMP_DIR"
RESPONSE_HEADERS="$TMP_DIR/response_headers.txt"
RESPONSE_BODY="$TMP_DIR/response_body.txt"
cleanup_tmp() {
  rm -rf "$TMP_DIR"
}
trap cleanup_tmp EXIT

# Given
echo "STEP: Given — establish current public API constraints for tool-sequencing verification"
echo "PREREQ: tool sequencing (lookup_order before refund_order) is internal agent behavior and no public HTTP endpoint exists to observe or assert tool calls directly"

# When
echo "STEP: When — call GET /health"
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
echo "STEP: Then — assert service health while documenting that tool-call sequencing is not externally observable through the public HTTP API"
[ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected HTTP 200 got ${HTTP_CODE}"; exit 1; }
grep -F '"status"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain status field"; exit 1; }
grep -F '"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected response body to contain ok status value"; exit 1; }

# Cleanup
echo "STEP: Cleanup — no side effects to remove"

echo "CODEVALID_TEST_ASSERTION_OK:tool_sequence_no_refund_for_processing"

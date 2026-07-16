#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
TMP_DIR="$(mktemp -d)"
LAST_RESPONSE_HEADERS="$TMP_DIR/last_response_headers.txt"
LAST_RESPONSE_BODY="$TMP_DIR/last_response_body.txt"
ITERATION=1

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}

trap cleanup_tmp EXIT

# Given
echo "STEP: Given — prepare repeated stateless health endpoint verification"
echo "PREREQ: using BASE_URL=${BASE_URL} for 5 sequential GET /health calls"

# When
echo "STEP: When — send 5 sequential GET requests to /health"
while [ "$ITERATION" -le 5 ]; do
  RESPONSE_HEADERS="$TMP_DIR/response_headers_${ITERATION}.txt"
  RESPONSE_BODY="$TMP_DIR/response_body_${ITERATION}.txt"

  echo "REQUEST_HEADERS: Accept: application/json"
  echo "REQUEST_BODY: <empty>"
  HTTP_CODE="$(curl -sS -D "$RESPONSE_HEADERS" -o "$RESPONSE_BODY" -w '%{http_code}' \
    -X GET "$BASE_URL/health" \
    -H 'Accept: application/json')"
  echo "RESPONSE_STATUS: iteration ${ITERATION} => ${HTTP_CODE}"
  echo "RESPONSE_HEADERS:"
  cat "$RESPONSE_HEADERS"
  echo "RESPONSE_BODY:"
  cat "$RESPONSE_BODY"

  cp "$RESPONSE_HEADERS" "$LAST_RESPONSE_HEADERS"
  cp "$RESPONSE_BODY" "$LAST_RESPONSE_BODY"

  [ "$HTTP_CODE" = "200" ] || { echo "ASSERTION_FAILED: expected iteration ${ITERATION} HTTP 200 got ${HTTP_CODE}"; exit 1; }
  grep -F '"status":"ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || grep -F '"status": "ok"' "$RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected iteration ${ITERATION} response body to contain JSON status ok"; exit 1; }

  ITERATION=$((ITERATION + 1))
done

# Then
echo "STEP: Then — assert all repeated calls remained stable with HTTP 200 and ok payload"
[ -f "$LAST_RESPONSE_BODY" ] || { echo "ASSERTION_FAILED: expected final response body artifact to exist"; exit 1; }
grep -F '"status":"ok"' "$LAST_RESPONSE_BODY" >/dev/null 2>&1 || grep -F '"status": "ok"' "$LAST_RESPONSE_BODY" >/dev/null 2>&1 || { echo "ASSERTION_FAILED: expected final repeated-call response body to contain JSON status ok"; exit 1; }

# Cleanup
echo "STEP: Cleanup — no stateful cleanup required for stateless health check"

echo "CODEVALID_TEST_ASSERTION_OK:health_endpoint_stability_under_repeated_calls"

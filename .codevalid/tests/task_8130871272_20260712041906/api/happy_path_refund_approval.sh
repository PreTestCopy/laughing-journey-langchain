#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/happy_path_refund_approval_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/happy_path_refund_approval_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-12345"
REQUESTED_AMOUNT="89.99"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because refund approval is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'approved' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:happy_path_refund_approval"
else
  echo "Requested refund scenario 'happy_path_refund_approval' cannot be validated via public HTTP API: repo exposes only GET /health, not refund processing for order ${REQUESTED_ORDER_ID}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

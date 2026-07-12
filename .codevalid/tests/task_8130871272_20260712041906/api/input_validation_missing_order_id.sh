#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/input_validation_missing_order_id_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/input_validation_missing_order_id_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
MISSING_ORDER_PROMPT_EXPECTATION="order number or order ID"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because refund input validation is not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F 'order ID' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:input_validation_missing_order_id"
else
  echo "Requested refund scenario 'input_validation_missing_order_id' cannot be validated via public HTTP API: repo exposes only GET /health, not refund input validation prompting for ${MISSING_ORDER_PROMPT_EXPECTATION}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

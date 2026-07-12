#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/business_rules_full_refund_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/business_rules_full_refund_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given — current service exposes only GET /health; no public refund-resolution HTTP API exists.
REQUESTED_ORDER_ID="ORD-ELIGIBLE-001"
REQUESTED_AMOUNT="249.50"

# When — call the only available public API entry point discovered in the repo.
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then — verify the service is reachable, and fail clearly because full-refund business rules are not exposed via HTTP.
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
if grep -F '249.50' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "CODEVALID_TEST_ASSERTION_OK:business_rules_full_refund"
else
  echo "Requested refund scenario 'business_rules_full_refund' cannot be validated via public HTTP API: repo exposes only GET /health, not full-refund eligibility processing for order ${REQUESTED_ORDER_ID}." >&2
  exit 1
fi

# Cleanup — no persistent side effects created.

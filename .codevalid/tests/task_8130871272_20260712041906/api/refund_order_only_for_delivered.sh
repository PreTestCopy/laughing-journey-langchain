#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/refund_order_only_for_delivered_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/refund_order_only_for_delivered_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# The delivered-only refund rule is internal business logic. Because this repo exposes
# only GET /health publicly, there is no HTTP endpoint through which to verify that
# refund_order is withheld for shipped status.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: delivered-only refund rule cannot be asserted over public HTTP because no refund endpoint exists; only GET /health is available' >&2
exit 1

# Cleanup
# No persistent side effects were created.

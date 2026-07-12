#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/processing_order_refund_denied_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/processing_order_refund_denied_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# The repo's public HTTP API exposes only GET /health. There is no curl-reachable
# refund resolution endpoint to verify denial for processing orders.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: cannot verify processing-order refund denial because no refund HTTP endpoint exists; only GET /health is public' >&2
exit 1

# Cleanup
# No persistent side effects were created.

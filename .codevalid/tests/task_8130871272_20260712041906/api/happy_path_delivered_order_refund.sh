#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/happy_path_delivered_order_refund_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/happy_path_delivered_order_refund_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# Public HTTP surface inspection shows this service exposes only GET /health.
# No refund-processing HTTP endpoint exists for order ORD-12345, so the requested
# delivered-order refund flow cannot be exercised through a public API.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: refund workflow is not exposed via public HTTP API; only GET /health exists in server.py' >&2
exit 1

# Cleanup
# No persistent side effects were created.

#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/minimal_customer_request_handling_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/minimal_customer_request_handling_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# Minimal customer-request handling pertains to invoke()/agent behavior, but the service
# does not expose invoke over HTTP. The only public API entrypoint is GET /health.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: minimal refund request parsing cannot be exercised via curl because invoke is not exposed as an HTTP API; only GET /health exists' >&2
exit 1

# Cleanup
# No persistent side effects were created.

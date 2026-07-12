#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/tool_call_sequence_enforcement_${CASE_SUFFIX}.json"
STATUS_FILE="/tmp/tool_call_sequence_enforcement_${CASE_SUFFIX}.status"
cleanup_files() { rm -f "$RESPONSE_FILE" "$STATUS_FILE"; }
trap cleanup_files EXIT

# Given
# Tool-call ordering (lookup_order before refund_order) is internal agent behavior.
# This repository exposes only GET /health as a public HTTP endpoint, so the sequence
# cannot be observed through curl-based E2E API testing.

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$BASE_URL/health" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
grep -F '"status":"ok"' "$RESPONSE_FILE" >/dev/null
printf '%s\n' 'UNSUPPORTED_TEST_SURFACE: internal tool-call sequence is not observable via public HTTP API; only GET /health exists in this service' >&2
exit 1

# Cleanup
# No persistent side effects were created.

#!/usr/bin/env sh
set -eu
BASE_URL="${BASE_URL:-http://app:6713}"
CASE_SUFFIX="$(date +%s)-$$"
RESPONSE_FILE="/tmp/health_check_response_structure_${CASE_SUFFIX}.body"
STATUS_FILE="/tmp/health_check_response_structure_${CASE_SUFFIX}.status"
cleanup_files() {
  rm -f "$RESPONSE_FILE" "$STATUS_FILE"
}
trap cleanup_files EXIT

# Given
HEALTH_URL="$BASE_URL/health"

# When
curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' "$HEALTH_URL" > "$STATUS_FILE"

# Then
STATUS="$(cat "$STATUS_FILE")"
[ "$STATUS" = "200" ]
python - "$RESPONSE_FILE" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text())
assert isinstance(payload, dict), "response is not a JSON object"
assert list(payload.keys()) == ["status"], f"unexpected keys: {list(payload.keys())}"
assert isinstance(payload["status"], str), "status is not a string"
assert payload["status"] == "ok", f"unexpected status value: {payload['status']}"
PY

echo "CODEVALID_TEST_ASSERTION_OK:health_check_response_structure"

# Cleanup
# No persistent side effects to clean up for GET /health.

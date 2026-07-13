#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
API_URL="${API_URL%/}"
ACCESS_TOKEN="${ACCESS_TOKEN:-}"
TOP_K="${TOP_K:-5}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-1}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-60}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

json_get() {
  local path="$1"
  python -c '
import json
import sys

path = sys.argv[1].split(".")
value = json.load(sys.stdin)

for part in path:
    if isinstance(value, list):
        value = value[int(part)]
    elif isinstance(value, dict):
        value = value[part]
    else:
        raise SystemExit(f"Invalid JSON path segment: {part!r}")

if isinstance(value, (dict, list)):
    print(json.dumps(value))
elif value is None:
    print("null")
else:
    print(value)
' "$path"
}

print_section() {
  printf "\n== %s ==\n" "$1"
}

upload_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Demo file not found: $path" >&2
    exit 1
  fi

  echo "Uploading $path" >&2
  local response
  response="$(
    curl -sSf -X POST \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -F "files=@${path}" \
      "${API_URL}/api/v1/documents/upload"
  )"

  local document_id
  document_id="$(printf '%s' "$response" | json_get "items.0.document_id")"
  local initial_status
  initial_status="$(printf '%s' "$response" | json_get "items.0.status")"
  echo "  document_id=${document_id} initial_status=${initial_status}" >&2

  printf '%s\n' "$document_id"
}

wait_ready() {
  local document_id="$1"
  local started_at
  started_at="$(date +%s)"
  local last_status=""

  while true; do
    local response
    response="$(
      curl -sSf \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        "${API_URL}/api/v1/documents/${document_id}"
    )"
    local status
    status="$(printf '%s' "$response" | json_get "status")"
    if [[ "$status" != "$last_status" ]]; then
      echo "  ${document_id} status=${status}"
      last_status="$status"
    fi

    if [[ "$status" == "READY" ]]; then
      return 0
    fi

    if [[ "$status" == "FAILED" ]]; then
      local error_message
      error_message="$(
        printf '%s' "$response" | python -c '
import json
import sys

data = json.load(sys.stdin)
print(data.get("error_message") or "unknown ingestion error")
'
      )"
      echo "  ${document_id} FAILED: ${error_message}" >&2
      return 1
    fi

    local now
    now="$(date +%s)"
    local elapsed
    elapsed=$((now - started_at))
    if (( elapsed >= POLL_TIMEOUT_SECONDS )); then
      echo "Timed out after ${POLL_TIMEOUT_SECONDS}s waiting for ${document_id}. Last status=${status}" >&2
      return 1
    fi

    sleep "$POLL_INTERVAL_SECONDS"
  done
}

ask_question() {
  local question_text="$1"
  shift
  local payload
  payload="$(
    python - "$question_text" "$@" <<'PY'
import json
import sys

question = sys.argv[1]
document_ids = sys.argv[2:]
print(json.dumps({"question": question, "document_ids": document_ids}))
PY
  )"

  curl -sSf -X POST "${API_URL}/api/v1/questions/ask" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

print_answer() {
  local response="$1"
  if [[ -z "${response//[[:space:]]/}" ]]; then
    echo "Empty response body from ${API_URL}/api/v1/questions/ask." >&2
    return 1
  fi

  JSON_RESPONSE="$response" python - "$TOP_K" <<'PY'
import json
import os
import sys

top_k = int(sys.argv[1])
raw = os.environ.get("JSON_RESPONSE", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"Failed to parse ask response JSON: {exc}. Raw: {raw[:500]!r}")

print(f"question_id: {data.get('question_id')}")
print("answer:")
print(data.get("answer", ""))

sources = data.get("sources") or []
print(f"sources (showing up to {top_k}):")
if not sources:
    print("  (none)")
    raise SystemExit(0)

for index, source in enumerate(sources[:top_k], start=1):
    parts = [
        f"document_id={source.get('document_id')}",
        f"chunk_index={source.get('chunk_index')}",
    ]
    if source.get("distance") is not None:
        parts.append(f"distance={source.get('distance')}")
    print(f"  {index}. " + ", ".join(parts))
PY
}

print_history_snippet() {
  local response="$1"
  if [[ -z "${response//[[:space:]]/}" ]]; then
    echo "Empty response body from ${API_URL}/api/v1/questions/history." >&2
    return 2
  fi

  JSON_RESPONSE="$response" python - <<'PY'
import json
import os
import sys

raw = os.environ.get("JSON_RESPONSE", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise SystemExit(f"Failed to parse history response JSON: {exc}. Raw: {raw[:500]!r}")

items = data.get("items") or []

if not items:
    print("No question history items returned.")
    raise SystemExit(0)

latest = items[0]
question = " ".join((latest.get("question") or "").split())
answer = " ".join((latest.get("answer") or "").split())
if len(answer) > 80:
    answer = answer[:80].rstrip() + "..."

print(f"latest: Q=\"{question}\" | A=\"{answer}\"")
PY
}

require_command curl
require_command python

if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "Set ACCESS_TOKEN to a verified user's bearer token before running the demo." >&2
  exit 1
fi

if ! [[ "$TOP_K" =~ ^[0-9]+$ ]] || (( TOP_K < 1 )); then
  echo "TOP_K must be an integer >= 1. Received: $TOP_K" >&2
  exit 1
fi

if ! [[ "$POLL_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || (( POLL_TIMEOUT_SECONDS < 1 )); then
  echo "POLL_TIMEOUT_SECONDS must be an integer >= 1. Received: $POLL_TIMEOUT_SECONDS" >&2
  exit 1
fi

if ! [[ "$POLL_INTERVAL_SECONDS" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "POLL_INTERVAL_SECONDS must be a positive number. Received: $POLL_INTERVAL_SECONDS" >&2
  exit 1
fi

print_section "FastAPI RAG Demo"
echo "API_URL=${API_URL}"
echo "TOP_K=${TOP_K} (used for source display)"
echo "POLL_INTERVAL_SECONDS=${POLL_INTERVAL_SECONDS}"
echo "POLL_TIMEOUT_SECONDS=${POLL_TIMEOUT_SECONDS}"

print_section "1) Health check"
if ! curl -sf "${API_URL}/api/v1/health" >/dev/null; then
  echo "Health check failed: could not reach ${API_URL}/api/v1/health." >&2
  echo "Start the stack first (for example: docker compose up -d)." >&2
  exit 1
fi
echo "API is healthy."

print_section "2) Upload demo documents"
declare -a document_ids=()
for file_path in demo/sample.txt demo/sample.md demo/sample.pdf; do
  document_ids+=("$(upload_file "$file_path")")
done
echo "Uploaded ${#document_ids[@]} document(s)."

print_section "3) Poll document status until READY"
for document_id in "${document_ids[@]}"; do
  wait_ready "$document_id"
done

print_section "4) Ask question (restricted to uploaded documents)"
question_one="What ingestion job statuses are tracked for crash recovery?"
answer_one="$(ask_question "$question_one" "${document_ids[@]}")"
echo "question: $question_one"
print_answer "$answer_one"

print_section "5) Ask fallback question (restricted to uploaded documents)"
question_two="The docs mention cosine distance and ingestion jobs. What is the on-call pager phone number?"
answer_two="$(ask_question "$question_two" "${document_ids[@]}")"
echo "question: $question_two"
print_answer "$answer_two"

print_section "6) Fetch question history snippet"
history_response="$(
  curl -sSf \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${API_URL}/api/v1/questions/history?limit=5&offset=0"
)"
print_history_snippet "$history_response"

echo
echo "Demo completed successfully."

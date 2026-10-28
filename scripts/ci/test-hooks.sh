#!/usr/bin/env bash
# Self-test of the agent hooks in .claude/hooks: feeds them the JSON a tool call would send
# and checks the exit code. Run in CI and locally with `bash scripts/ci/test-hooks.sh`.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
export CLAUDE_PROJECT_DIR="$root"
state="$root/.claude/state"
phase_file="$state/tdd-phase"
had_phase=""
[[ -f "$phase_file" ]] && had_phase="$(cat "$phase_file")"
trap 'if [[ -n "$had_phase" ]]; then echo "$had_phase" > "$phase_file"; else rm -f "$phase_file"; fi' EXIT

failures=0

# expect <phase|none> <path> <expected exit code>
expect() {
  local phase="$1" path="$2" want="$3" got
  if [[ "$phase" == none ]]; then rm -f "$phase_file"; else mkdir -p "$state" && echo "$phase" > "$phase_file"; fi
  set +e
  printf '{"tool_input":{"file_path":"%s/%s"}}' "$root" "$path" | "$root/.claude/hooks/tdd-guard.sh" 2>/dev/null
  got=$?
  set -e
  if [[ "$got" == "$want" ]]; then
    echo "ok   tdd-guard phase=$phase $path -> $got"
  else
    echo "FAIL tdd-guard phase=$phase $path -> $got, expected $want"
    failures=$((failures + 1))
  fi
}

expect none  backend/tests/unit/test_retrieval.py 0
expect red   backend/tests/unit/test_retrieval.py 0
expect green backend/tests/unit/test_retrieval.py 2
expect green backend/tests/conftest.py 2
expect green frontend/src/features/chat/ChatView.test.tsx 2
expect green frontend/e2e/ask-question.spec.ts 2
expect green evals/datasets/questions.yaml 2
expect green backend/src/assistant/services/retrieval.py 0
expect green frontend/src/features/chat/ChatView.tsx 0
expect green docs/features/F-01-walking-skeleton/plan.md 0

[[ "$failures" -eq 0 ]] || { echo "$failures hook test(s) failed"; exit 1; }
echo "All hook tests passed."

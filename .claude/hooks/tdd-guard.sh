#!/usr/bin/env bash
# PreToolUse hook: in the green phase of /tdd, test and evaluation files are read-only (ADR 0009).
# The phase is set by the /tdd skill in .claude/state/tdd-phase; without that file nothing is blocked.
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
phase_file="$root/.claude/state/tdd-phase"
# shellcheck source=scripts/lib/test-paths.sh
source "$root/scripts/lib/test-paths.sh"

[[ -f "$phase_file" ]] || exit 0
[[ "$(tr -d '[:space:]' < "$phase_file")" == "green" ]] || exit 0

path="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
[[ -n "$path" ]] || exit 0
rel="${path#"$root"/}"

if is_test_path "$rel"; then
  echo "tdd-guard: '$rel' is a test or evaluation file and the /tdd green phase is active." >&2
  echo "Make the code pass the tests as written. If a test is wrong, stop and go back to the red phase with a separate test(...) commit." >&2
  exit 2
fi
exit 0

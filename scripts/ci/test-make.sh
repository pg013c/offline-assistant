#!/usr/bin/env bash
# Self-test of the Makefile's development entry point. Runs only `make dev-preflight`,
# which checks configuration and ports without starting any server.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
failures=0

# preflight <env(1) arguments>: no .env file and unused ports, so only the given environment counts.
preflight() {
  env "$@" make -C "$root" --no-print-directory dev-preflight \
    ENV_FILE="$scratch/missing.env" API_PORT=59998 UI_PORT=59999 2>&1
}

check() {
  local name="$1" ok="$2"
  if [[ "$ok" == yes ]]; then echo "ok   $name"; else echo "FAIL $name"; failures=$((failures + 1)); fi
}

set +e
output="$(preflight -u ASSISTANT_DATA_DIR)"
status=$?
set -e
check "dev refuses to start without ASSISTANT_DATA_DIR" \
  "$([[ $status -ne 0 && "$output" == *ASSISTANT_DATA_DIR* ]] && echo yes || echo no)"

set +e
output="$(preflight ASSISTANT_DATA_DIR="$scratch/data")"
status=$?
set -e
check "dev starts when ASSISTANT_DATA_DIR is set" "$([[ $status -eq 0 ]] && echo yes || echo no)"

# llm_preflight <env(1) arguments>: checks the local LLM's file and port without starting it.
llm_preflight() {
  env "$@" make -C "$root" --no-print-directory llm-preflight \
    ENV_FILE="$scratch/missing.env" LLM_PORT=59997 2>&1
}

set +e
output="$(llm_preflight ASSISTANT_MODELS_DIR="$scratch/no-models")"
status=$?
set -e
check "llm refuses to start without the pinned model file, naming make llm-models" \
  "$([[ $status -ne 0 && "$output" == *"make llm-models"* ]] && echo yes || echo no)"

set +e
output="$(env make -C "$root" --no-print-directory eval-answers ENV_FILE="$scratch/missing.env" LLM_PORT=59996 2>&1)"
status=$?
set -e
check "eval-answers refuses to run without the model server, naming make llm" \
  "$([[ $status -ne 0 && "$output" == *"make llm"* ]] && echo yes || echo no)"

[[ "$failures" -eq 0 ]] || { echo "$failures Makefile test(s) failed"; exit 1; }
echo "All Makefile tests passed."

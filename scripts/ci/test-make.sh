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
  env -u LLM_MODEL "$@" make -C "$root" --no-print-directory llm-preflight \
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

# judge_preflight <env(1) arguments>: checks the judge's file and port without starting it.
judge_preflight() {
  env "$@" make -C "$root" --no-print-directory judge-preflight \
    ENV_FILE="$scratch/missing.env" JUDGE_PORT=59995 2>&1
}

set +e
output="$(judge_preflight ASSISTANT_MODELS_DIR="$scratch/no-models")"
status=$?
set -e
check "judge refuses to start without the pinned judge file, naming make judge-models" \
  "$([[ $status -ne 0 && "$output" == *"make judge-models"* ]] && echo yes || echo no)"

check "judge serves on JUDGE_PORT as qwen3-30b-a3b" \
  "$(make -C "$root" --no-print-directory -n judge JUDGE_PORT=59994 ASSISTANT_MODELS_DIR="$scratch" 2>/dev/null \
    | grep -q -- "--port 59994.*--alias qwen3-30b-a3b\|--alias qwen3-30b-a3b.*--port 59994" && echo yes || echo no)"

judge_recipe="$(make -C "$root" --no-print-directory -n judge ASSISTANT_MODELS_DIR="$scratch" 2>/dev/null)"
check "judge thinks before it rules (ADR 0023)" \
  "$([[ "$judge_recipe" == *"--alias qwen3-30b-a3b"* && "$judge_recipe" != *"--reasoning-budget 0"* ]] && echo yes || echo no)"

# llm_recipe <make arguments>: what `make llm` would run, without the environment's LLM_MODEL.
llm_recipe() {
  env -u LLM_MODEL make -C "$root" --no-print-directory -n llm \
    ENV_FILE="$scratch/missing.env" ASSISTANT_MODELS_DIR="$scratch" "$@" 2>&1
}

check "llm serves qwen3-8b when no model is named" \
  "$([[ "$(llm_recipe)" == *"--alias qwen3-8b "* ]] && echo yes || echo no)"

# Every served model in the registry (F-09b, ADR 0024) and its pinned file under the models dir.
served_models=(
  "qwen3-8b llm/Qwen--Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf"
  "qwen3.5-9b llm/unsloth--Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf"
  "qwen3.6-35b-a3b llm/ggml-org--Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-Q4_K_M.gguf"
  "gemma-4-26b-a4b llm/google--gemma-4-26B-A4B-it-qat-q4_0-gguf/gemma-4-26B_q4_0-it.gguf"
  "ternary-bonsai-2-27b llm/prism-ml--Ternary-Bonsai-2-27B-gguf/Ternary-Bonsai-2-27B-Q2_0.gguf"
)
shared_recipe=""
for entry in "${served_models[@]}"; do
  read -r name file <<<"$entry"
  recipe="$(llm_recipe LLM_MODEL="$name")"
  check "llm serves $name from its pinned file under its name, thinking off (ADR 0024)" \
    "$([[ "$recipe" == *"-m \"$scratch/$file\""* && "$recipe" == *"--alias $name "* \
      && "$recipe" == *"--reasoning off"* && "$recipe" == *"--ctx-size 16384"* \
      && "$recipe" == *"--n-gpu-layers 99"* && "$recipe" == *"--jinja"* ]] && echo yes || echo no)"
  # With the file and the name taken out, every model's server command must be the same. The
  # preflight before it names the model on purpose, so only the llama-server command counts.
  generic="$(sed -n '/^llama-server/,$p' <<<"$recipe")"
  generic="${generic//$scratch\/$file/FILE}"
  generic="${generic//--alias $name /--alias NAME }"
  shared_recipe="${shared_recipe:-$generic}"
  check "llm gives $name no flag of its own" "$([[ "$generic" == "$shared_recipe" ]] && echo yes || echo no)"
done

for name in no-such-model fake-extractive; do
  set +e
  output="$(llm_recipe LLM_MODEL="$name")"
  status=$?
  set -e
  check "llm refuses LLM_MODEL=$name, listing the served models" \
    "$([[ $status -ne 0 && "$output" == *"$name"* && "$output" == *"qwen3-8b"* \
      && "$output" == *"gemma-4-26b-a4b"* && "$output" == *"ternary-bonsai-2-27b"* ]] && echo yes || echo no)"
done

set +e
output="$(llm_preflight ASSISTANT_MODELS_DIR="$scratch/no-models" LLM_MODEL=gemma-4-26b-a4b)"
status=$?
set -e
check "llm-preflight names the command that fetches the chosen model" \
  "$([[ $status -ne 0 && "$output" == *"make llm-models LLM_MODEL=gemma-4-26b-a4b"* ]] && echo yes || echo no)"

check "llm-models fetches only the chosen model" \
  "$(env -u LLM_MODEL make -C "$root" --no-print-directory -n llm-models ENV_FILE="$scratch/missing.env" \
    ASSISTANT_MODELS_DIR="$scratch" LLM_MODEL=qwen3.5-9b 2>/dev/null \
    | grep -q -- "--llm qwen3.5-9b" && echo yes || echo no)"

[[ "$failures" -eq 0 ]] || { echo "$failures Makefile test(s) failed"; exit 1; }
echo "All Makefile tests passed."

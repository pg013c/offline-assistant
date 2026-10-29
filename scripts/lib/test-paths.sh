#!/usr/bin/env bash
# Which repository paths count as tests or evaluation data (ADR 0009). The evaluation
# harness in evals/harness is code like any other; its datasets, tests, Promptfoo config and
# corpus pins are evaluation inputs (TEST-22).
# Shared by the tdd-guard hook and the CI commit check, so both apply the same rule.

# is_test_path <path relative to the repository root>
is_test_path() {
  case "$1" in
    backend/tests/*|frontend/e2e/*|frontend/src/test/*|scripts/ci/test-*|evals/datasets/*|evals/tests/*|evals/promptfoo/*|evals/corpus.json|*.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx|test_*.py|*/test_*.py|conftest.py|*/conftest.py)
      return 0 ;;
  esac
  return 1
}

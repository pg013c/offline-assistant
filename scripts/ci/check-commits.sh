#!/usr/bin/env bash
# Checks every commit in a range against the commit rules in docs/workflow.md and ADR 0009:
#   1. the subject follows Conventional Commits,
#   2. feat, fix and refactor commits do not modify tests or evaluation data
#      (tests change only in test(...) commits, before the code that passes them).
# Usage: check-commits.sh <base> <head>
set -euo pipefail

base="${1:?usage: check-commits.sh <base> <head>}"
head="${2:?usage: check-commits.sh <base> <head>}"
root="$(git rev-parse --show-toplevel)"
# shellcheck source=scripts/lib/test-paths.sh
source "$root/scripts/lib/test-paths.sh"

subject_re='^(feat|fix|refactor|test|docs|build|ci|chore|perf|style|revert)(\([A-Za-z0-9-]+\))?!?: [^ ].{0,99}$'
failures=0

while read -r sha; do
  subject="$(git log -1 --format=%s "$sha")"
  short="$(git rev-parse --short "$sha")"

  # Merge commits are made by the human through GitHub and keep GitHub's subject.
  if [[ "$(git rev-list --parents -n 1 "$sha" | wc -w)" -gt 2 ]]; then
    continue
  fi

  if [[ ! "$subject" =~ $subject_re ]]; then
    echo "::error::$short '$subject' is not a Conventional Commit subject (type(scope): summary, max 100 chars)"
    failures=$((failures + 1))
    continue
  fi

  type="${subject%%[(:!]*}"
  if [[ "$type" == feat || "$type" == fix || "$type" == refactor ]]; then
    while read -r path; do
      if [[ -n "$path" ]] && is_test_path "$path"; then
        echo "::error::$short '$subject' modifies test path '$path'. Tests change only in test(...) commits (ADR 0009)."
        failures=$((failures + 1))
      fi
    done < <(git diff-tree --no-commit-id --name-only -r "$sha")
  fi
done < <(git rev-list --reverse "$base..$head")

if [[ "$failures" -gt 0 ]]; then
  echo "$failures commit rule violation(s) in $base..$head"
  exit 1
fi
echo "All commits in $base..$head follow the commit rules."

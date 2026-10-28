#!/usr/bin/env bash
# PostToolUse hook: format the file the agent just edited with the project's formatter.
# Does nothing until the backend/frontend projects and their tools exist (F-00).
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
path="$(jq -r '.tool_input.file_path // empty')"
[[ -n "$path" && -f "$path" ]] || exit 0
rel="${path#"$root"/}"

case "$rel" in
  backend/*.py)
    if [[ -f "$root/backend/pyproject.toml" ]] && command -v uv >/dev/null; then
      uv run --directory "$root/backend" ruff format --quiet "$path" >/dev/null 2>&1
      uv run --directory "$root/backend" ruff check --fix --quiet "$path" >/dev/null 2>&1
    fi
    ;;
  frontend/*.ts|frontend/*.tsx|frontend/*.css|frontend/*.json)
    if [[ -d "$root/frontend/node_modules" ]] && command -v pnpm >/dev/null; then
      pnpm --dir "$root/frontend" exec prettier --write --log-level silent "$path" >/dev/null 2>&1
    fi
    ;;
esac
exit 0

#!/usr/bin/env bash
# API contract check (ADR 0005): regenerates the OpenAPI schema and TypeScript types into a
# temporary directory and compares them with the files in frontend/src/api.
# Fails when the backend changed its API without `make api-client` being run.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
committed="$root/frontend/src/api"
fresh="$(mktemp -d)"
trap 'rm -rf "$fresh"' EXIT

make -C "$root" --no-print-directory api-client API_OUT="$fresh" >/dev/null

failures=0
for file in openapi.json schema.d.ts; do
  if ! diff -u "$committed/$file" "$fresh/$file" >/dev/null 2>&1; then
    echo "::error file=frontend/src/api/$file::frontend/src/api/$file is out of date with the backend API. Run 'make api-client' and commit the result."
    diff -u "$committed/$file" "$fresh/$file" | head -40 || true
    failures=$((failures + 1))
  fi
done

[[ "$failures" -eq 0 ]] || exit 1
echo "Generated API client is up to date."

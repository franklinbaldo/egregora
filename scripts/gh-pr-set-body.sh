#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/gh-pr-set-body.sh <pr-number> [body...]" >&2
  exit 1
fi

pr_number="$1"
shift || true

repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)

if [[ $# -gt 0 ]]; then
  body="$*"
else
  body=$(cat)
fi

gh api "repos/$repo/pulls/$pr_number" \
  -X PATCH \
  --raw-field "body=$body"

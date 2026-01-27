#!/usr/bin/env bash
# Enable auto-merge for Jules PRs
# Usage: enable-auto-merge.sh <pr_number>
#
# Environment variables required:
#   GH_TOKEN - GitHub token with PR write permissions

set -euo pipefail

PR_NUMBER="${1:?PR number required}"

# Check if author is Jules
author_login=$(gh pr view "$PR_NUMBER" --json author --jq '.author.login')
case "$author_login" in
  "google-labs-jules[bot]"|"app/google-labs-jules"|"google-labs-jules")
    echo "✅ PR #$PR_NUMBER is authored by Jules ($author_login)"
    ;;
  *)
    echo "⏭️ PR #$PR_NUMBER is authored by $author_login; skipping auto-merge"
    exit 0
    ;;
esac

# Mark draft PRs as ready
is_draft=$(gh pr view "$PR_NUMBER" --json isDraft --jq '.isDraft')
if [ "$is_draft" = "true" ]; then
  echo "📝 PR #$PR_NUMBER is draft; marking ready for review"
  gh pr ready "$PR_NUMBER"
fi

# Enable auto-merge
echo "🔀 Enabling auto-merge for PR #$PR_NUMBER"
gh pr merge "$PR_NUMBER" --auto --delete-branch

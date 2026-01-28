#!/usr/bin/env bash
# Enable auto-merge for Jules PRs
# Usage: enable-auto-merge.sh <pr_number>
#
# Environment variables required:
#   GH_TOKEN - GitHub token with PR write permissions
#
# Jules PRs are detected by:
#   1. PR body containing jules.google.com URL (primary)
#   2. OR author is Jules bot (fallback)

set -euo pipefail

PR_NUMBER="${1:?PR number required}"

# Get PR details
pr_data=$(gh pr view "$PR_NUMBER" --json author,body)
author_login=$(echo "$pr_data" | jq -r '.author.login')
pr_body=$(echo "$pr_data" | jq -r '.body // ""')

# Check if it's a Jules PR (URL in body OR bot author)
is_jules_pr=false

# Primary: Check for Jules URL in body
if echo "$pr_body" | grep -qE 'jules\.google\.com/(session|task)'; then
  echo "✅ PR #$PR_NUMBER has Jules URL in body"
  is_jules_pr=true
fi

# Fallback: Check if author is Jules bot
case "$author_login" in
  "google-labs-jules[bot]"|"app/google-labs-jules"|"google-labs-jules")
    echo "✅ PR #$PR_NUMBER is authored by Jules ($author_login)"
    is_jules_pr=true
    ;;
esac

if [ "$is_jules_pr" = "false" ]; then
  echo "⏭️ PR #$PR_NUMBER is not a Jules PR; skipping auto-merge"
  exit 0
fi

# Mark draft PRs as ready
is_draft=$(gh pr view "$PR_NUMBER" --json isDraft --jq '.isDraft')
if [ "$is_draft" = "true" ]; then
  echo "📝 PR #$PR_NUMBER is draft; marking ready for review"
  gh pr ready "$PR_NUMBER"
fi

# Enable auto-merge
echo "🔀 Enabling auto-merge for PR #$PR_NUMBER"
gh pr merge "$PR_NUMBER" --auto --delete-branch

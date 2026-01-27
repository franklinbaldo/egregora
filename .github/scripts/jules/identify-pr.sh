#!/usr/bin/env bash
# Identify PR number from a workflow_run event
# Usage: identify-pr.sh <event_file>
#
# Outputs (via GITHUB_OUTPUT):
#   has_pr=true|false
#   pr_number=<number>
#
# Environment variables required:
#   GH_TOKEN - GitHub token
#   GITHUB_REPOSITORY - owner/repo
#   GITHUB_OUTPUT - output file path

set -euo pipefail

EVENT_FILE="${1:?Event file path required}"

# Try to get PR URL directly from the event
PR_URL=$(jq -r '.workflow_run.pull_requests[0].url // empty' "$EVENT_FILE")

# If not present, try to find a PR by matching head SHA
if [[ -z "$PR_URL" ]]; then
  HEAD_SHA=$(jq -r '.workflow_run.head_sha // empty' "$EVENT_FILE")
  if [[ -n "$HEAD_SHA" ]]; then
    echo "🔍 Looking for PR with head SHA: $HEAD_SHA"
    PR_URL=$(curl -s -H "Authorization: Bearer $GH_TOKEN" \
      "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls?state=all" \
      | jq -r --arg sha "$HEAD_SHA" '.[] | select(.head.sha == $sha) | .url' | head -n1)
  fi
fi

if [[ -z "$PR_URL" ]]; then
  echo "ℹ️ No pull request associated with this workflow_run"
  echo "has_pr=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

# Fetch PR details
PR_JSON=$(curl -s -H "Authorization: Bearer $GH_TOKEN" "$PR_URL")
PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number // empty')

if [[ -z "$PR_NUMBER" ]]; then
  echo "⚠️ Failed to determine PR number from $PR_URL"
  echo "has_pr=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "✅ Found PR #$PR_NUMBER"
echo "has_pr=true" >> "$GITHUB_OUTPUT"
echo "pr_number=$PR_NUMBER" >> "$GITHUB_OUTPUT"

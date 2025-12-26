#!/bin/bash
# Script to manually trigger auto-merge workflow for bot PRs
# This is useful for testing or retrying auto-merge on existing PRs

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <pr_number>"
    echo "Example: $0 1694"
    exit 1
fi

PR_NUMBER=$1

echo "🔄 Triggering auto-merge workflow for PR #$PR_NUMBER..."
echo ""

# Check if gh CLI is available
if command -v gh &> /dev/null; then
    echo "Using GitHub CLI to trigger workflow..."
    gh workflow run auto-merge.yml -f pr_number=$PR_NUMBER
    echo "✅ Workflow triggered! Check https://github.com/franklinbaldo/egregora/actions"
else
    echo "❌ GitHub CLI (gh) not found."
    echo ""
    echo "To trigger the workflow manually:"
    echo "1. Go to https://github.com/franklinbaldo/egregora/actions/workflows/auto-merge.yml"
    echo "2. Click 'Run workflow'"
    echo "3. Enter PR number: $PR_NUMBER"
    echo "4. Click 'Run workflow'"
    echo ""
    echo "Or install gh CLI: https://cli.github.com/"
fi

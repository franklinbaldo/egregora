# Automatic Code Review Setup

This document explains how to set up automatic code reviews that trigger on every push.

## Current Setup

The repository includes a GitHub Actions workflow (`.github/workflows/auto-review.yml`) that:

1. **Triggers on push** to feature branches (`claude/**`, `feature/**`, `fix/**`)
2. **Finds the associated PR** for the branch
3. **Posts a comment** to trigger the code review bot
4. **Requests reviewers** (optional, if configured)

## How It Works

### For chatgpt-codex-connector Bot

The `chatgpt-codex-connector` bot appears to be a GitHub App that provides automated code reviews. To integrate it with the auto-review workflow:

#### Option 1: Comment-Triggered Reviews

If the bot watches PR comments for trigger phrases:

1. The workflow is already configured to post comments automatically
2. Configure the bot to watch for: "🤖 Automatic code review requested"
3. The bot should respond to each push with a new review

#### Option 2: GitHub App Integration

If the bot uses GitHub's Pull Request Review API:

1. Install the chatgpt-codex-connector GitHub App on this repository
2. Configure the app to trigger on `pull_request` and `push` events
3. Grant necessary permissions (contents: read, pull_requests: write)

#### Option 3: Webhook Integration

If the bot provides a webhook URL:

1. Get the webhook URL from the bot's configuration
2. Add it as a repository secret: `CODEX_WEBHOOK_URL`
3. Update the workflow to call the webhook:

```yaml
- name: Trigger CodeX via Webhook
  if: steps.find-pr.outputs.pr_exists == 'true'
  run: |
    curl -X POST "${{ secrets.CODEX_WEBHOOK_URL }}" \
      -H "Content-Type: application/json" \
      -d '{
        "repository": "${{ github.repository }}",
        "pr_number": ${{ steps.find-pr.outputs.pr_number }},
        "sha": "${{ github.sha }}"
      }'
```

## Configuration

### Setting Up Auto-Reviewers (Optional)

To automatically request reviews from specific GitHub users:

1. Go to: **Settings → Secrets and variables → Actions → Variables**
2. Create a new variable: `AUTO_REVIEWERS`
3. Set value to comma-separated usernames: `user1,user2,user3`

### Customizing Trigger Branches

Edit `.github/workflows/auto-review.yml` to change which branches trigger reviews:

```yaml
on:
  push:
    branches:
      - 'claude/**'     # All claude branches
      - 'feature/**'    # All feature branches
      - 'your-pattern/**'  # Add your patterns
```

## Verifying Setup

After pushing a commit to a PR branch:

1. Check the **Actions** tab for workflow runs
2. Look for "Auto Code Review on Push" workflow
3. Verify it found the PR and posted a comment
4. Check if the codex bot responded with a review

## Troubleshooting

### Bot doesn't respond to workflow comments

- Check if the bot is properly installed as a GitHub App
- Verify bot has permissions: `pull_requests: write`, `contents: read`
- Check bot's trigger configuration (comment patterns, events)

### Workflow can't find the PR

- Ensure the PR is open (not draft or closed)
- Check the branch name matches the trigger patterns
- Review workflow logs in the Actions tab

### Rate limiting

If pushing frequently, the bot might hit rate limits. Consider:
- Adding a cooldown check (workflow already includes 1-minute deduplication)
- Configuring the bot to batch reviews
- Using PR review requests instead of comments

## Alternative: Continuous Review Bot

If you want more sophisticated review automation, consider these alternatives:

1. **CodeRabbit** - AI-powered code review on every PR
2. **Danger** - Automated PR checks and reviews
3. **ReviewDog** - Automated code review tool
4. **SonarCloud** - Code quality and security analysis

## Questions?

Check the chatgpt-codex-connector documentation for:
- Installation instructions
- API/webhook endpoints
- Trigger configuration
- Supported comment commands

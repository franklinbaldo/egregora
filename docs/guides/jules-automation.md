# Jules Automated Code Reviews

Egregora includes automated Jules (Google's AI coding agent) integration for continuous code review on every pull request.

## Overview

When you open a PR, Jules automatically:
1. Reviews the code changes
2. Checks for quality, security, and testing issues
3. Creates a follow-up PR with improvements (if needed)
4. Posts feedback directly on your PR

## Setup

### Prerequisites

1. **Google Cloud Project** with Jules API access
2. **Jules API Key** from your Google Cloud Console

### Configuration

1. **Add the JULES_API_KEY secret to your GitHub repository:**

   ```bash
   # Go to: Settings → Secrets and variables → Actions → New repository secret
   Name: JULES_API_KEY
   Value: <your-jules-api-key>
   ```

2. **The workflow is already configured** in `.github/workflows/jules-review.yml`

3. **That's it!** Jules will now review every PR automatically.

## How It Works

### Trigger Conditions

Jules review triggers on:
- ✅ New PR opened
- ✅ PR updated with new commits
- ✅ PR reopened

Jules does NOT trigger on:
- ❌ Draft PRs
- ❌ Dependabot PRs
- ❌ Branches starting with `draft/`

### Review Focus Areas

Jules checks:
- **Code Quality** - Maintainability, readability, best practices
- **Test Coverage** - Missing tests, edge cases
- **Security** - Privacy issues, vulnerabilities
- **Performance** - Optimization opportunities
- **Documentation** - Missing or unclear docs
- **Standards** - Adherence to ruff, black, mypy rules

### What Jules Does

1. **Analyzes** the PR branch against base branch
2. **Creates a session** with detailed review prompt
3. **Posts a comment** on the PR with session ID
4. **Works asynchronously** (~10 minutes)
5. **May create a follow-up PR** with fixes (mode: AUTO_CREATE_PR)

## Example Workflow

```
Developer opens PR #42
    ↓
Jules workflow triggers automatically
    ↓
Jules session created: "Review PR #42: Add user auth"
    ↓
Bot comments on PR with session ID
    ↓
Jules analyzes code (~10 min)
    ↓
Jules creates PR #43: "Jules review improvements for PR #42"
    ↓
Developer reviews and merges Jules' suggestions
    ↓
Original PR #42 is ready to merge
```

## Monitoring Jules Sessions

### Check Session Status

```bash
# Get session details
python .claude/skills/jules-api/jules_client.py get <session-id>

# List all sessions
python .claude/skills/jules-api/jules_client.py list
```

### Session States

- **QUEUED** - Waiting to start
- **PLANNING** - Generating review plan
- **IN_PROGRESS** - Actively reviewing
- **COMPLETED** - Review finished
- **FAILED** - Error occurred

### Send Additional Feedback

```bash
python .claude/skills/jules-api/jules_client.py message <session-id> \
  "Please also check for SQL injection vulnerabilities"
```

## Troubleshooting

### Jules workflow fails

**Symptoms:** Workflow shows red ❌, PR comment says "Jules Review Failed"

**Common causes:**
1. Missing `JULES_API_KEY` secret
2. Invalid API key
3. Jules API quota exceeded
4. Network issues

**Solutions:**
```bash
# Verify secret is set in GitHub
# Settings → Secrets → JULES_API_KEY should exist

# Check workflow logs
# Actions tab → Failed workflow → Expand "Create Jules review session"

# Manually trigger Jules if needed
python .claude/skills/jules-api/jules_client.py create \
  "Review PR #42" \
  franklinbaldo \
  egregora \
  --branch feature-branch
```

### Jules creates too many PRs

**Problem:** Jules creates a new PR for every commit

**Solution:** The workflow already filters synchronize events to prevent spam. If you want to disable Jules temporarily:

```yaml
# Edit .github/workflows/jules-review.yml
# Change:
on:
  pull_request:
    types: [opened]  # Remove synchronize
```

### Jules suggestions are too aggressive

**Problem:** Jules suggests major refactoring when you want minor fixes

**Solution:** Customize the review prompt in `jules-review.yml`:

```yaml
# Edit the REVIEW_PROMPT in jules-review.yml
REVIEW_PROMPT="Code review for PR focusing ONLY on:
- Security issues
- Critical bugs
- Test coverage gaps

Do NOT suggest refactoring or style changes."
```

## Cost Management

### API Usage

Jules API calls count against your Google Cloud quota. Each PR review costs approximately:
- 1 session creation
- ~10-30 LLM calls (depends on code size)

### Rate Limiting

The workflow runs on every PR event. For high-traffic repos:

1. **Add a concurrency limit:**
   ```yaml
   concurrency:
     group: jules-review-${{ github.event.pull_request.number }}
     cancel-in-progress: true
   ```

2. **Limit to specific labels:**
   ```yaml
   if: contains(github.event.pull_request.labels.*.name, 'needs-review')
   ```

3. **Require manual trigger:**
   ```yaml
   on:
     workflow_dispatch:
       inputs:
         pr_number:
           required: true
   ```

## Disabling Jules Automation

To disable automatic Jules reviews:

```bash
# Option 1: Delete the workflow
rm .github/workflows/jules-review.yml

# Option 2: Disable in GitHub UI
# Settings → Actions → Disable the "Jules Code Review" workflow

# Option 3: Add a skip label
# Add this to jules-review.yml:
if: |
  !contains(github.event.pull_request.labels.*.name, 'skip-jules')
```

## Best Practices

1. **Review Jules' PRs carefully** - Jules is a tool, not a replacement for human review
2. **Provide feedback** - Use `jules_client.py message` to guide Jules
3. **Monitor costs** - Check Google Cloud billing for Jules API usage
4. **Customize prompts** - Tailor review focus to your project needs
5. **Combine with human review** - Jules + human review = best quality

## Advanced Configuration

### Custom Review Criteria

Edit the `REVIEW_PROMPT` in `.github/workflows/jules-review.yml`:

```yaml
REVIEW_PROMPT="Code review with extra focus on:
- Egregora-specific privacy guarantees (UUID5 anonymization)
- Polars DataFrame performance
- LLM prompt injection risks
- Cost optimization (minimize LLM calls)

Check against project standards in CLAUDE.md"
```

### Approval Required Mode

If you want Jules to wait for approval before making changes:

```yaml
python .claude/skills/jules-api/jules_client.py create \
  "${REVIEW_PROMPT}" \
  "${REPO_OWNER}" \
  "${REPO_NAME}" \
  --branch "${PR_BRANCH}" \
  --require-plan-approval \  # Add this flag
  --automation-mode MANUAL   # Don't auto-create PR
```

Then manually approve:
```bash
python .claude/skills/jules-api/jules_client.py get <session-id>
# Review the plan
python .claude/skills/jules-api/jules_client.py approve-plan <session-id>
```

## Related Documentation

- [Jules API Skill](/.claude/skills/jules-api/README.md)
- [Jules Client Reference](/.claude/skills/jules-api/SKILL.md)
- [Jules Examples](/.claude/skills/jules-api/examples.md)
- [GitHub Actions](https://docs.github.com/actions)

## Support

For issues with:
- **Jules API** - See [Google Jules Docs](https://developers.google.com/jules)
- **Workflow** - Check GitHub Actions logs
- **Integration** - Open issue in this repo with `jules` label

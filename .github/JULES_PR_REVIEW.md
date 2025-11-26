# Jules Automated PR Review

This repository uses [Jules](https://jules.google/) (Google's AI coding agent) to automatically review pull requests. Jules analyzes PRs against egregora's architecture, conventions, and best practices, posting detailed feedback as PR comments.

## How It Works

1. **Trigger:** When a PR is opened, updated, or reopened
2. **Review:** Jules API analyzes the PR against egregora-specific criteria
3. **Comment:** Automated review posted as a PR comment with actionable feedback

## Setup

### Prerequisites

1. **Connect Repository to Jules:**
   - Visit https://jules.google.com/
   - Sign in with your Google account
   - Click "Connect to GitHub" and authorize the Jules app
   - Select the `franklinbaldo/egregora` repository

2. **Generate Jules API Key:**
   - Go to https://jules.google.com/settings/api
   - Click "Generate API Key"
   - Copy the generated key

3. **Add GitHub Secret:**
   - Go to https://github.com/franklinbaldo/egregora/settings/secrets/actions
   - Click "New repository secret"
   - Name: `JULES_API_KEY`
   - Value: (paste the Jules API key)
   - Click "Add secret"

### Verification

Once set up, the workflow will automatically run on new PRs. You can verify:

1. Open a test PR
2. Check the "Actions" tab for the `jules-pr-review` workflow
3. Wait for the workflow to complete (~1-5 minutes)
4. Look for a comment from the GitHub Actions bot with Jules' review

## Review Criteria

Jules reviews PRs specifically for egregora's architecture and standards:

### 1. Privacy & Security
- ✅ Privacy stage runs BEFORE LLM processing
- ✅ No PII leaks to external APIs
- ✅ Proper UUID-based anonymization

### 2. Code Quality
- ✅ Line length: 110 chars max
- ✅ Ruff compliance (proper exception handling, no BLE001)
- ✅ Type hints where appropriate
- ✅ Proper error propagation

### 3. Architecture Compliance
- ✅ Input/output adapters implement correct protocols
- ✅ Pure functional transforms (Table → Table)
- ✅ Schema validation with `validate_ir_schema()`
- ✅ IR_MESSAGE_SCHEMA columns preserved

### 4. Testing
- ✅ Unit tests for new functionality
- ✅ Integration tests with VCR cassettes
- ✅ Tests pass in CI

### 5. Documentation
- ✅ Breaking changes documented in CLAUDE.md
- ✅ Docstrings for public APIs
- ✅ Clear commit messages

## Usage

### Automatic Review

By default, Jules reviews every PR automatically. No action required!

### Skip Review

To skip Jules review on a specific PR, add `[skip-jules]` to the PR title:

```
[skip-jules] WIP: Experimental feature
```

### Manual Review (CLI)

You can also manually trigger reviews from the Jules UI:

1. Go to https://jules.google.com/
2. Select the `franklinbaldo/egregora` source
3. Enter a prompt like: "Review the current PR #123"
4. Jules will analyze and provide feedback

### Handling Reviews

Jules reviews include:

- **Summary:** High-level assessment
- **Issues:** Specific problems with file:line references
- **Suggestions:** Actionable code improvements
- **Approval:** ✅ LGTM / ⚠️ Minor issues / ❌ Needs work

Treat Jules reviews as suggestions, not requirements. Use your judgment to apply feedback appropriately.

## Troubleshooting

### Workflow Not Running

**Symptom:** No Jules review appears on PRs

**Solutions:**
1. Check the Actions tab for error logs
2. Verify `JULES_API_KEY` secret is set correctly
3. Confirm repository is connected at https://jules.google.com/
4. Check if PR title contains `[skip-jules]`
5. Ensure PR is not from a `jules/` branch (infinite loop protection)

### "Repository not found in Jules sources"

**Cause:** Repository not connected to Jules

**Solution:**
1. Go to https://jules.google.com/
2. Click "Add Source" → "GitHub"
3. Authorize and select `franklinbaldo/egregora`
4. Wait a few minutes for synchronization
5. Retry the workflow

### Timeout / No Review Content

**Cause:** Jules session taking too long or not returning content

**Solutions:**
1. Check Jules session status at https://jules.google.com/
2. Large PRs may timeout (default: 10 minutes)
3. Adjust `MAX_POLL_ATTEMPTS` in `jules-pr-review.mjs` if needed
4. Consider breaking large PRs into smaller chunks

### API Rate Limits

**Cause:** Hitting Jules API rate limits

**Solution:**
- Jules API is in alpha; rate limits may apply
- Space out PR updates if hitting limits
- Contact Jules support for enterprise limits

## Architecture

```
.github/
├── workflows/
│   └── jules-pr-review.yml    # GitHub Action workflow definition
└── scripts/
    ├── jules-pr-review.mjs     # Jules API integration script
    ├── package.json            # Node.js dependencies
    └── package-lock.json       # Locked dependency versions
```

### Workflow File (`.github/workflows/jules-pr-review.yml`)

- Triggers on PR events (opened, synchronize, reopened)
- Skips Jules-created branches to avoid loops
- Sets up Node.js environment
- Runs the review script

### Review Script (`.github/scripts/jules-pr-review.mjs`)

- Finds egregora source in Jules
- Starts a Jules session with egregora-specific prompt
- Polls for review completion (max 10 minutes)
- Posts review as PR comment

## Customization

### Adjust Review Prompt

Edit the `EGREGORA_REVIEW_PROMPT` constant in `jules-pr-review.mjs` to customize review criteria.

### Change Timeout

Adjust `MAX_POLL_ATTEMPTS` and `POLL_INTERVAL_MS` in `jules-pr-review.mjs`:

```javascript
const POLL_INTERVAL_MS = 5000;  // Poll every 5 seconds
const MAX_POLL_ATTEMPTS = 120;  // 10 minutes max (120 * 5s)
```

### Add Review Labels

Extend the script to apply GitHub labels based on Jules' approval:

```javascript
// After posting comment
if (reviewText.includes("✅ LGTM")) {
  await octokit.issues.addLabels({
    owner, repo, issue_number: prNumber,
    labels: ["jules-approved"]
  });
}
```

## Cost & Limits

- **Jules API:** Free during alpha; future pricing TBD
- **GitHub Actions:** Free for public repos; private repos have monthly limits
- **Recommendations:**
  - Use on PRs with significant changes
  - Skip on WIP/draft PRs to conserve quota
  - Monitor usage in Actions tab

## Security

- **API Key:** Stored as GitHub secret (encrypted at rest)
- **Permissions:** Workflow has `contents: read`, `pull-requests: write`
- **Scope:** Jules can only read repo content and post PR comments
- **Privacy:** Jules may send PR diffs to Google APIs; ensure compliance with your policies

## Future Enhancements

Potential improvements:

- [ ] Auto-approve PRs that pass Jules review with no issues
- [ ] Request changes via GitHub review API (not just comments)
- [ ] Integrate with egregora's existing pre-commit hooks
- [ ] Post summary statistics (lines changed, test coverage, etc.)
- [ ] Support for incremental reviews (only changed files since last review)

## Resources

- **Jules Documentation:** https://jules.google.com/docs/
- **Jules API Reference:** https://developers.google.com/jules/api
- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Egregora Architecture:** See `CLAUDE.md` in repository root

## Support

For issues with:

- **Jules functionality:** https://jules.google.com/support
- **Egregora-specific questions:** Open an issue in this repository
- **GitHub Actions:** https://github.com/franklinbaldo/egregora/actions

---

**Note:** Jules API is in `v1alpha` and subject to change. Monitor the [changelog](https://jules.google/docs/changelog/) for breaking changes.

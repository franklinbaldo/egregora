# AI-Powered Automated PR Review

This repository uses two AI-powered systems for automated pull request reviews:

1. **Gemini** - Full-context review using Repomix + manual trigger support
2. **Jules** - Google's AI coding agent with API-based review

Both are tuned specifically for egregora's architecture, privacy-first principles, and coding conventions.

## Quick Comparison

| Feature | Gemini | Jules |
|---------|--------|-------|
| **Context** | Full repo (Repomix) | PR diff only |
| **Trigger** | Automatic + `@gemini` | Automatic only |
| **Model** | Gemini 2.0/3.0 | Jules (multi-agent) |
| **Fork Support** | ✅ Yes (secure) | ❌ Limited |
| **Interactive** | ✅ Comment replies | ❌ No |
| **Setup** | API key only | GitHub connection + API |
| **Cost** | Pay-per-call | Alpha (free) |

**Recommendation:** Use **Gemini** for comprehensive reviews with full codebase context. Use **Jules** for lightweight async reviews when the API is available.

---

## 1. Gemini PR Review

### Features

- **Full repository context** via Repomix
- **Secure fork handling** with maintainer approval
- **Interactive reviews** via `@gemini` comments
- **Egregora-tuned** for privacy, architecture, and patterns
- **Smart chunking** for large PRs

### Setup

#### 1.1 Get Gemini API Key

1. Visit https://aistudio.google.com/apikey
2. Create a new API key
3. Copy the key

#### 1.2 Add GitHub Secret

1. Go to https://github.com/franklinbaldo/egregora/settings/secrets/actions
2. Click "New repository secret"
3. Name: `GEMINI_API_KEY`
4. Value: (paste your API key)
5. Click "Add secret"

#### 1.3 (Optional) Configure Model

By default, Gemini uses `gemini-3-pro-preview`. To change:

1. Go to https://github.com/franklinbaldo/egregora/settings/variables/actions
2. Click "New repository variable"
3. Name: `GEMINI_MODEL`
4. Value: `gemini-2.0-flash-exp` (or other model)
5. Click "Add variable"

### Usage

#### Automatic Review

Gemini automatically reviews every non-draft PR:

1. Open a PR
2. Wait 1-3 minutes for context generation
3. Review appears as a comment

#### Manual Trigger

For forks or specific requests:

1. Comment `@gemini` on any PR
2. Optionally add instructions: `@gemini focus on security`
3. Gemini will analyze and respond

#### Skip Review

To prevent Gemini from reviewing a specific PR:

1. Mark PR as "Draft"
2. Or don't trigger `@gemini` manually

### Review Format

Gemini provides structured feedback:

```markdown
## 📋 Summary
High-level assessment of the PR

## 🔍 Critical Issues
- **src/file.py:45** - 🔴 Privacy bypass detected (MUST FIX)

## ⚠️ Important Issues
- **src/file.py:90** - 🟡 Using pandas instead of Ibis

## 💡 Suggestions
- **src/file.py:120** - 🟢 Consider renaming variable

## 🏗️ Architecture & Egregora Patterns
Comments on architecture compliance

## 📝 Breaking Changes
Verification of CLAUDE.md documentation

## 🛠️ Action Items
- [ ] Fix privacy issue
- [ ] Add tests
```

### Egregora-Specific Checks

Gemini is trained to flag:

#### 1. Privacy & Security (CRITICAL)
- ✅ Privacy stage runs BEFORE LLM
- ✅ No PII leaks to external APIs
- ✅ Proper UUID-based anonymization

#### 2. Code Quality
- ✅ Line length: 110 chars max
- ✅ No bare `except Exception:` (BLE001)
- ✅ Type hints where appropriate
- ✅ Specific exception catching

#### 3. Architecture
- ✅ Ibis for table operations (not pandas)
- ✅ Functional transforms: `Table → Table`
- ✅ IR_MESSAGE_SCHEMA preserved
- ✅ VectorStore facade for RAG
- ✅ Config in `.egregora/config.yml`

#### 4. Testing
- ✅ Unit tests for new functionality
- ✅ VCR cassettes for API calls
- ✅ Tests pass with `--retrieval-mode=exact`

#### 5. Documentation
- ✅ Breaking changes in CLAUDE.md
- ✅ Docstrings for public APIs

### Workflow Details

**File:** `.github/workflows/gemini-pr-review.yml`

**Steps:**
1. Security checks (fork detection, collaborator verification)
2. Checkout base + PR head (secure worktree)
3. Generate repo context with Repomix
4. Fetch PR diff + comment history
5. Call Gemini API with structured prompt
6. Post review as PR comment

**Security:** Fork PRs require maintainer approval via `@gemini` comment.

---

## 2. Jules PR Review

### Features

- **Lightweight** - PR diff only (no full repo context)
- **Fast** - Completes in ~1-5 minutes
- **Egregora-tuned** prompt with architecture rules
- **API-based** - Uses Jules API (Google's coding agent)

### Setup

#### 2.1 Connect Repository to Jules

1. Visit https://jules.google.com/
2. Sign in with your Google account
3. Click "Connect to GitHub"
4. Authorize the Jules app
5. Select `franklinbaldo/egregora` repository

#### 2.2 Generate API Key

1. Go to https://jules.google.com/settings/api
2. Click "Generate API Key"
3. Copy the key

#### 2.3 Add GitHub Secret

1. Go to https://github.com/franklinbaldo/egregora/settings/secrets/actions
2. Click "New repository secret"
3. Name: `JULES_API_KEY`
4. Value: (paste your API key)
5. Click "Add secret"

### Usage

#### Automatic Review

Jules reviews every PR automatically:

1. Open a PR
2. Wait ~1-5 minutes
3. Jules posts review as comment

#### Skip Review

Add `[skip-jules]` to PR title:

```
[skip-jules] WIP: Experimental feature
```

### Review Format

Jules provides actionable feedback:

```markdown
### 🤖 Jules Automated Review

Review content with egregora-specific analysis...

---
Powered by Jules | Skip by adding [skip-jules] to PR title
```

### Workflow Details

**File:** `.github/workflows/jules-pr-review.yml`

**Steps:**
1. Find egregora source in Jules
2. Start review session with egregora-specific prompt
3. Poll for completion (max 10 minutes)
4. Post review as PR comment

**Limitations:**
- No full repo context (diff only)
- No interactive comments
- Fork support limited

---

## Comparison & When to Use Each

### Use Gemini When:

- ✅ You need **full repository context** for complex architectural reviews
- ✅ You're reviewing **fork PRs** (secure handling)
- ✅ You want **interactive reviews** (`@gemini do X`)
- ✅ The PR touches multiple interconnected files
- ✅ You need context from other parts of the codebase

### Use Jules When:

- ✅ You want a **second opinion** alongside Gemini
- ✅ The PR is **self-contained** (single feature/fix)
- ✅ You prefer **API-based automation** over UI setup
- ✅ You're already using Jules for other tasks

### Using Both (Recommended)

The workflows don't conflict—run both for maximum coverage:

1. **Gemini** provides deep architectural review with full context
2. **Jules** provides independent validation

Both flag issues; more signals = better quality.

---

## Troubleshooting

### Gemini Issues

#### "Missing GEMINI_API_KEY"

**Solution:**
1. Check secret exists: https://github.com/franklinbaldo/egregora/settings/secrets/actions
2. Ensure name is exactly `GEMINI_API_KEY` (case-sensitive)
3. Re-run workflow after adding secret

#### Review Not Posted

**Check:**
1. Is PR marked as "Draft"? (Gemini skips drafts)
2. Check Actions tab for errors
3. Verify Repomix generated context (check artifact on failure)

#### "User is not a collaborator" (on forks)

**Expected:** Only maintainers can trigger `@gemini` on fork PRs for security.

**Solution:** Maintainer must comment `@gemini` to approve review.

### Jules Issues

#### "Repository not found in Jules sources"

**Solution:**
1. Visit https://jules.google.com/
2. Ensure repo is connected
3. Wait a few minutes for sync
4. Retry workflow

#### Timeout / No Review Content

**Solutions:**
1. Check Jules session at https://jules.google.com/
2. Large PRs may timeout (default: 10 minutes)
3. Consider splitting PR into smaller chunks

### Both Issues

#### Workflow Not Running

**Check:**
1. Workflow file exists in `.github/workflows/`
2. PR is not from a `jules/` or `gemini/` branch
3. API key secrets are set correctly
4. View Actions tab for detailed logs

---

## Architecture

```
.github/
├── workflows/
│   ├── gemini-pr-review.yml    # Gemini workflow (Repomix + full context)
│   └── jules-pr-review.yml     # Jules workflow (API-based)
└── scripts/
    ├── gemini-pr-review.js     # Gemini API integration (CommonJS)
    ├── jules-pr-review.mjs     # Jules API integration (ESM)
    ├── package.json            # Dependencies for both
    └── package-lock.json       # Locked versions
```

### Dependencies

Both scripts share a common `package.json`:

```json
{
  "dependencies": {
    "@google/generative-ai": "^0.21.0",  // Gemini API
    "@octokit/rest": "^21.0.2",          // GitHub API (both)
    "dotenv": "^16.4.5"                  // Environment vars
  }
}
```

---

## Customization

### Adjust Gemini Prompt

Edit `.github/scripts/gemini-pr-review.js`:

```javascript
function generatePrompt(repomix, patch, chat) {
  // Customize egregora-specific checks here
}
```

### Adjust Jules Prompt

Edit `.github/scripts/jules-pr-review.mjs`:

```javascript
const EGREGORA_REVIEW_PROMPT = `
  // Customize review criteria here
`;
```

### Change Models

**Gemini:** Set `GEMINI_MODEL` repository variable (default: `gemini-3-pro-preview`)

**Jules:** Controlled by Jules backend (no user selection)

### Adjust Timeouts

**Gemini:** Edit `timeout-minutes: 15` in workflow file

**Jules:** Edit `MAX_POLL_ATTEMPTS` in `jules-pr-review.mjs`

---

## Cost & Limits

### Gemini

- **API Costs:** Pay-per-call via Google AI Studio
- **GitHub Actions:** Free for public repos
- **Recommendation:** Monitor usage at https://aistudio.google.com/

### Jules

- **API Costs:** Free during alpha (future pricing TBD)
- **GitHub Actions:** Free for public repos
- **Limits:** API rate limits may apply

---

## Security & Privacy

### Gemini

- **API Key:** Encrypted in GitHub secrets
- **Permissions:** `contents: read`, `pull-requests: write`
- **Fork Safety:** Requires maintainer approval
- **Data:** PR diffs sent to Google Gemini API

### Jules

- **API Key:** Encrypted in GitHub secrets
- **Permissions:** `contents: read`, `pull-requests: write`
- **Data:** PR diffs sent to Jules API

### Important

Both systems send PR content to external APIs. Ensure compliance with your privacy policies before enabling.

---

## Future Enhancements

Potential improvements:

- [ ] Auto-approve PRs passing both reviews
- [ ] Request changes via GitHub review API
- [ ] Integrated review summaries (Gemini + Jules)
- [ ] Cost tracking and budget alerts
- [ ] Custom review templates per file type

---

## Resources

- **Gemini API:** https://ai.google.dev/
- **Jules Documentation:** https://jules.google.com/docs/
- **Jules API Reference:** https://developers.google.com/jules/api
- **GitHub Actions:** https://docs.github.com/en/actions
- **Egregora Architecture:** See `CLAUDE.md` in repository root

---

## Support

For issues with:

- **Gemini functionality:** https://ai.google.dev/support
- **Jules functionality:** https://jules.google.com/support
- **Egregora-specific questions:** Open an issue in this repository
- **GitHub Actions:** https://github.com/franklinbaldo/egregora/actions

---

**Note:** Both systems are in active development. Monitor changelogs for breaking changes:
- Gemini: https://ai.google.dev/gemini-api/docs/models
- Jules: https://jules.google/docs/changelog/

# Gemini PR Review Workflow Diagnostic

## Issue Summary

The Gemini PR review workflow on PR #2294 failed with:
- **Failure Type**: `all_models_failed`
- **Selected Model**: unknown
- **Parse Response**: failure

## Root Cause Analysis

Based on the workflow code analysis:

### How the Workflow Works

1. **Model Cascade**: Tries 5 Gemini models sequentially:
   - `gemini-3-pro-preview` (primary)
   - `gemini-3-flash-preview` (if 3-pro fails)
   - `gemini-2.5-pro` (if both above fail)
   - `gemini-2.5-flash` (if all above fail)
   - `gemini-2.5-flash-lite` (last resort)

2. **Consolidation**: The `gemini_final` step picks the first successful response

3. **Parsing**: The `parse_combined` step extracts JSON from the response

### Why It Failed

When `gemini_final.outputs.outcome = 'failure'` and `gemini_final.outputs.model = 'unknown'`, it means **ALL 5 models failed**.

This suggests one of these issues:

#### 1. **API Key Issue** ⚠️ MOST LIKELY
```yaml
secrets.GEMINI_API_KEY
```
- **Expired**: API keys can expire
- **Invalid**: Key might be malformed
- **Quota Exhausted**: Free tier quota exceeded
- **Permissions**: Key doesn't have permission for these models

**Action**: Check in GitHub Settings → Secrets → `GEMINI_API_KEY`

#### 2. **Model Availability**
The models in use:
- `gemini-3-pro-preview` - **PREVIEW** (may be deprecated)
- `gemini-3-flash-preview` - **PREVIEW** (may be deprecated)
- `gemini-2.5-pro` - Newer model
- `gemini-2.5-flash` - Newer model
- `gemini-2.5-flash-lite` - Newer model

**Possible Issue**: Preview models might have been deprecated or renamed.

**Check**: https://ai.google.dev/gemini-api/docs/models/gemini

#### 3. **Rate Limiting**
If the repository has many PRs triggering Gemini reviews, Google might be rate-limiting the requests.

**Symptoms**:
- All models fail simultaneously
- Works after waiting a few minutes
- Happens during high activity periods

#### 4. **Prompt Size**
The workflow collects PR diffs with:
```bash
git diff "${BASE_SHA}...${HEAD_SHA}" --unified=1
```

If PR #2294 has a very large diff, it might exceed Gemini's token limits.

**Check**: How many files/lines changed in PR #2294?

## Diagnostic Steps

### 1. Check API Key
```bash
# In GitHub repository settings
Settings → Secrets and variables → Actions → GEMINI_API_KEY
```

**Verify**:
- Key exists
- Key is not expired
- Key has correct permissions

### 2. Check Model Names
Compare workflow model names with current Gemini API docs:
- https://ai.google.dev/gemini-api/docs/models/gemini

**Update** `.github/workflows/gemini-pr-review.yml` if models changed.

### 3. Check PR Size
```bash
# Check PR #2294 diff size
gh pr view 2294 --json additions,deletions
```

If very large, consider:
- Increasing `--unified=` context (or decreasing)
- Filtering out generated files
- Using `--stat` instead of full diff

### 4. Test Manually
```bash
# Export API key
export GEMINI_API_KEY="your-key"

# Test with a simple prompt
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}'
```

Expected: JSON response with generated text
If error: Check the error message for details

## Recommended Fixes

### Fix 1: Update Model Names
If preview models are deprecated, update to stable models:

```yaml
# Before
gemini_model: "gemini-3-pro-preview"

# After
gemini_model: "gemini-2.0-flash-exp"  # Or whatever is current
```

### Fix 2: Add Better Error Handling
The workflow should capture and display the actual API error:

```yaml
- name: Run Gemini PR Review (3 Pro)
  id: gemini_3_pro
  continue-on-error: true
  uses: google-github-actions/run-gemini-cli@v0
  with:
    gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
    gemini_model: "gemini-3-pro-preview"
    prompt: ${{ env.GEMINI_PROMPT }}

# Add error capture
- name: Capture Gemini Error
  if: steps.gemini_3_pro.outcome == 'failure'
  run: |
    echo "::error::Gemini 3 Pro failed: ${{ steps.gemini_3_pro.outputs }}"
```

### Fix 3: Fallback to Non-Preview Models First
Reorder models to try stable versions before preview:

```yaml
# Priority order (stable first):
1. gemini-2.5-flash
2. gemini-2.5-flash-lite
3. gemini-2.5-pro
4. gemini-3-flash-preview  # Only if stable versions fail
5. gemini-3-pro-preview    # Last resort
```

### Fix 4: Add Retry Logic
Add retries with exponential backoff for rate limits:

```yaml
- name: Run Gemini with Retry
  uses: nick-fields/retry@v2
  with:
    timeout_minutes: 5
    max_attempts: 3
    retry_on: error
    command: |
      # Gemini API call here
```

## Quick Fix for PR #2294

To unblock the specific PR:

1. **Manual trigger with @gemini**:
   ```
   Comment on PR #2294: @gemini please review
   ```
   This will retry the workflow.

2. **Check if API key is set**:
   The workflow shows it checks this:
   ```yaml
   if [ -z "${{ secrets.GEMINI_API_KEY }}" ]; then
     echo "::error::GEMINI_API_KEY secret is not set!"
   ```

3. **Skip Gemini review temporarily**:
   If urgent, can merge without Gemini review (it's a code review helper, not a gate).

## Long-term Solution

Consider migrating to more reliable alternatives:

1. **GitHub Copilot for PRs** (built-in GitHub feature)
2. **OpenAI GPT-4** (more stable API)
3. **Anthropic Claude** (via API)
4. **Self-hosted Llama models** (no API costs/limits)

## Related Files

- Workflow: `.github/workflows/gemini-pr-review.yml`
- PR: https://github.com/franklinbaldo/egregora/pull/2294
- Failed Run: Check GitHub Actions tab for detailed logs

---

**Created**: 2026-01-09
**Status**: Diagnostic complete, awaiting investigation of root cause

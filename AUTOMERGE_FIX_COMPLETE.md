# Auto-Merge Fix: Complete Investigation and Solution

## Problem Summary

Auto-merge was not working for Jules bot PRs. Despite having the auto-merge workflow, bot PRs remained in draft mode and auto-merge was never enabled.

## Affected PRs

**Initially investigated**: PR #1688 (WhatsApp parser exceptions)
- Status: Manually merged by franklinbaldo on 2025-12-26

**Currently affected** (as of 2025-12-26):
- PR #1694: ⚡ feat(tests): add benchmark for PII scrubbing
- PR #1693: 💎 Refactor Feed.to_xml to use declarative template
- PR #1692: 💣 refactor: structure exceptions in database module

All three are Jules bot PRs, in draft mode, with auto_merge = null.

## Root Causes Identified

### Issue #1: Silent API Failures (FIXED)

**Problem**: The auto-merge workflow steps were catching errors and logging them without failing the step. This made the workflow appear successful while the actual operations (draft conversion, auto-merge enablement) failed.

**Evidence**:
- Workflow showed "success" status
- Posted comment "Draft converted to ready for review"
- But PR remained in draft mode and auto_merge stayed null

**Fix**: Enhanced error handling in `.github/workflows/auto-merge.yml`
- Added try-catch blocks that explicitly fail the step on errors
- Added verification after each operation to ensure it succeeded
- Better error messages identifying permission or API issues

**Commit**: `763142f` - "fix: improve auto-merge workflow error handling and verification"

### Issue #2: Wrong Actor Check (FIXED)

**Problem**: The workflow job-level `if` condition checked `github.actor` (the workflow trigger) instead of the PR author. When commits were pushed to a bot PR by a human, `github.actor` was the human, causing the workflow to skip entirely.

**Evidence**:
- PR #1694 workflow run: actor = franklinbaldo, conclusion = skipped
- PR #1693 workflow run: actor = franklinbaldo, conclusion = skipped
- PR #1692 workflow run: actor = franklinbaldo, conclusion = skipped

**Fix**: Changed job-level condition to check PR author
```yaml
# Before
if: |
  github.event_name == 'workflow_dispatch' ||
  github.actor == 'google-labs-jules[bot]'

# After
if: |
  github.event_name == 'workflow_dispatch' ||
  github.event.pull_request.user.login == 'google-labs-jules[bot]'
```

**Commit**: `3ceb87f` - "fix: check PR author instead of workflow trigger actor in auto-merge"

## Files Modified

1. **`.github/workflows/auto-merge.yml`**
   - Enhanced "Convert draft to ready for review" step with error handling and verification
   - Enhanced "Enable auto-merge" step with error handling and verification
   - Fixed job-level `if` condition to check PR author instead of workflow trigger
   - Simplified step-level conditions to use PR author consistently

2. **`scripts/fix_pr_automerge.py`**
   - Manual fix script for stuck PRs
   - Can convert from draft and enable auto-merge via GitHub API

3. **`scripts/AUTOMERGE_FIX.md`** (original investigation)
   - Initial analysis and fix documentation

4. **`scripts/trigger_automerge.sh`** (new)
   - Helper script to manually trigger workflow for a PR

## How to Fix Existing PRs

### Option 1: Manually Trigger Workflow

The workflow now has proper checks and will run for bot PRs. To trigger it:

```bash
# If you have gh CLI installed:
gh workflow run auto-merge.yml -f pr_number=1694

# Or use the helper script:
bash scripts/trigger_automerge.sh 1694

# Without gh CLI:
# 1. Go to https://github.com/franklinbaldo/egregora/actions/workflows/auto-merge.yml
# 2. Click "Run workflow"
# 3. Enter PR number: 1694
# 4. Click "Run workflow"
```

Repeat for PRs #1693 and #1692.

### Option 2: Trigger by Pushing Empty Commit

```bash
git fetch origin bolt/pii-scrubbing-benchmark-12100648897199721694
git checkout bolt/pii-scrubbing-benchmark-12100648897199721694
git commit --allow-empty -m "trigger workflow"
git push
```

This will trigger the `pull_request` event with type `synchronize`, which runs the workflow.

### Option 3: Use Manual Fix Script

```bash
export GITHUB_TOKEN=<your_token_with_repo_permissions>
python scripts/fix_pr_automerge.py 1694
```

## How Auto-Merge Will Work Going Forward

1. **PR Creation**: Jules bot creates a draft PR

2. **Workflow Triggers**: Auto-merge workflow runs on:
   - `pull_request` events: opened, synchronize, reopened, ready_for_review
   - Manual trigger via workflow_dispatch

3. **Actor Check**: Workflow checks if PR author is a bot (not who triggered the workflow)

4. **Draft Conversion**: Workflow converts PR from draft to ready for review
   - ✅ Success verification added
   - ❌ Explicit failure if verification shows PR still in draft

5. **Auto-Merge Enable**: Workflow enables auto-merge with squash method
   - ✅ Success verification added
   - ❌ Explicit failure if verification shows auto_merge still null

6. **CI Passes**: All required checks pass

7. **Auto-Merge**: GitHub automatically merges the PR

## Verification

After workflow runs, verify with:

```bash
# Check PR status
curl -s "https://api.github.com/repos/franklinbaldo/egregora/pulls/1694" | \
  grep -E '"draft"|"auto_merge"|"mergeable_state"'

# Should show:
# "draft": false,
# "auto_merge": { ... },
# "mergeable_state": "clean"
```

Or check the PR on GitHub:
- ✅ Status should be "Ready for review" (not "Draft")
- ✅ Auto-merge badge should be visible
- ✅ Workflow logs should show "Successfully converted" and "Verified auto-merge is enabled"

## Remaining Considerations

### Potential Issue: Permissions

If the workflow still fails after these fixes, it may be due to:
- `GITHUB_TOKEN` lacking permissions for draft conversion or auto-merge
- Branch protection rules requiring approvals before auto-merge
- Organization/repository settings restricting bot auto-merge

Check workflow logs for specific error messages that will now be visible.

### Potential Issue: Branch Protection

If auto-merge requires approvals, the workflow includes an approval step that runs for bot PRs. Check that this step succeeds.

## Summary of All Fixes

1. ✅ Enhanced error handling with verification (commit `763142f`)
2. ✅ Fixed actor check to use PR author (commit `3ceb87f`)
3. ✅ Created manual fix script for stuck PRs
4. ✅ Created trigger helper script
5. ✅ Comprehensive documentation

**Next step**: Trigger the workflow for PRs #1694, #1693, and #1692 to verify the fixes work.

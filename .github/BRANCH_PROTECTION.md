# Branch Protection Rules Setup

This document explains how to configure branch protection rules for the `main` branch to enable automated workflows like auto-merge.

## Why Branch Protection?

Branch protection ensures code quality by requiring:
- ✅ All CI checks to pass before merging
- ✅ Code reviews (optional but recommended)
- ✅ Up-to-date branches
- 🤖 Enables GitHub's native auto-merge feature

---

## Required Status Checks

For the auto-merge workflow to function properly, configure these **required status checks**:

### Core Checks (Always Required)
- `Pre-commit Hooks` (includes Ruff lint, format, vulture, etc.)
- `Unit Tests (Python 3.12)`
- `E2E Tests`

### Optional Checks
- `Security Scan` - Dependency vulnerability scanning
- `Build Package` - Runs after tests pass

---

## Setup Instructions

### 1. Navigate to Settings

Go to your repository on GitHub:
```
Settings → Branches → Add branch protection rule
```

### 2. Configure Protection Rule

**Branch name pattern:** `main`

**Enable these settings:**

- ✅ **Require a pull request before merging**
  - Required approvals: `1` (recommended)
  - Dismiss stale reviews: ✅ (recommended)
  - Require review from Code Owners: (optional)

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - **Search and add these required checks:**
    - `Pre-commit Hooks`
    - `Unit Tests (Python 3.12)`
    - `E2E Tests`

- ✅ **Require conversation resolution before merging** (recommended)

- ✅ **Do not allow bypassing the above settings** (recommended for teams)

**Optional but recommended:**
- ✅ Require linear history (keeps git history clean)
- ✅ Require deployments to succeed (if using deployments)

### 3. Save Changes

Click **Create** or **Save changes**

---

## Verifying Setup

After configuring branch protection:

1. **Create a test PR** from a feature branch
2. **Check the PR page** - you should see:
   - Required checks listed at the bottom
   - "Merge" button disabled until checks pass
   - Auto-merge button available (if all checks pass)

3. **Test auto-merge:**
   - Wait for Dependabot, Renovate, or a Jules PR to appear
   - The auto-merge workflow should:
     - ✅ Enable auto-merge
     - 🎯 PR merges automatically when checks pass

---

## Troubleshooting

### Known Infrastructure Issues

#### `enable-auto-merge` Check Failure
If you see a CI failure named `enable-auto-merge`, be aware:
- **Cause:** This is typically an external status check (triggered by Renovate or GitHub Actions infrastructure) that fails when it expects the repository to allow auto-merge but Branch Protection rules are misconfigured or missing.
- **Resolution:**
  1. Verify Branch Protection rules match the "Setup Instructions" above.
  2. Ensure the "Allow auto-merge" setting is enabled in **Settings > General > Pull Requests**.
  3. If the check persists in failing on PRs not authored by Renovate/Dependabot, it is safe to ignore/override if all other Core Checks passed.

### Auto-merge not working?

**Error:** "Auto-merge requires branch protection rules"
- ✅ **Solution:** Enable branch protection as described above

**Error:** "Pull request is not mergeable"
- ✅ Check required status checks are passing
- ✅ Ensure branch is up to date with base branch
- ✅ Resolve any merge conflicts

### Which checks should be required?

**For CI speed, require only critical checks:**
- Pre-commit Hooks (includes Ruff linting + format)
- Unit Tests (Python 3.12)
- E2E Tests

**Don't require conditionally-run jobs:**
- Security scans (runs in parallel, non-blocking)
- Build package (only runs after tests pass)

GitHub's "Expected" checks feature (beta) can help with conditional jobs.

---

## Alternative: Repository Rulesets (New)

GitHub now offers **Rulesets** as a modern alternative to branch protection rules:

**Advantages:**
- More granular control
- Better support for conditional checks
- Can apply to multiple branches
- Better bypass controls

**To use Rulesets instead:**
1. Go to `Settings → Rules → Rulesets`
2. Create a new ruleset targeting `main`
3. Configure the same protections as above

---

## Auto-merge Security Considerations

The auto-merge workflow is configured to:
- ✅ **Only merge patch and minor updates** (not major versions)
- ✅ **Only run for Dependabot/Renovate** (not untrusted actors)
- ✅ **Wait for all required checks** before merging
- ✅ **Uses rebase merge** for linear history (falls back to merge commit if rebase fails)

**Major updates still require manual review** to prevent breaking changes from being auto-merged.

---

## Further Reading

- [GitHub Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Auto-merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
- [Repository Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

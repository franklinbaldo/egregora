# Regression Detection System

Automatically detects when code is accidentally reverted to earlier states.

## Problem It Solves

Sometimes when fixing bugs or resolving merge conflicts, code can accidentally be reverted to an earlier version, losing recent improvements. This happened with PR #2691 which accidentally reverted 325 lines of features added just 1.5 hours earlier.

## How It Works

The regression detector:

1. **Examines staged files** (files about to be committed)
2. **Computes content hashes** for each file
3. **Checks recent git history** (last 30 days by default)
4. **Finds exact matches** - if the staged content matches an earlier commit
5. **Alerts the developer** with details about the potential regression

## When It Runs

### 1. Pre-Commit Hook (Local Development)

Runs automatically when you commit:

```bash
git commit -m "your message"
```

If a regression is detected, you'll see:

```
⚠️  WARNING: Potential code regression detected!

The following files match earlier commits:

📄 .team/repo/features/logging.py
   Matches commit: e252d68
   From: 2026-01-20T11:58:52+00:00
   Author: Claude <noreply@anthropic.com>
   Message: "refactor: migrate to per-session tool usage logs"

❓ This could be:
   1. ✅ Intentional revert (OK)
   2. ❌ Accidental regression (BAD)

Continue with commit anyway? (y/N):
```

You can then:
- Type `n` to abort and review
- Type `y` to proceed (if intentional revert)

### 2. GitHub Actions (CI/CD)

Runs automatically on every pull request, detecting regressions from remote bots like Jules.

## Usage

### Run Manually

Check for regressions in your current staged changes:

```bash
python .github/scripts/detect_regression.py
```

Options:
- `--lookback-days 30` - How far back to check (default: 30 days)
- `--non-interactive` - Run without prompting (for CI)

### Bypass if Needed

If you're doing an intentional revert:

```bash
# Option 1: Answer 'y' when prompted
git commit -m "revert: intentional rollback of feature X"

# Option 2: Skip pre-commit hooks (not recommended)
git commit --no-verify -m "intentional revert"
```

### What Files Are Checked

The script checks:
- ✅ All `.py` files
- ✅ All files in `.team/repo/`
- ❌ Skips: `.md`, `.txt`, `.json`, `.csv`, `.lock`, `.gitignore`

## Examples

### Case 1: Accidental Regression (Bad)

You're fixing a bug and accidentally revert recent logging improvements:

```
⚠️  WARNING: Regression detected!
📄 .team/repo/features/logging.py matches e252d68 from 2 hours ago

Continue? (y/N): n  ← You abort and investigate
```

**Outcome:** You discover the accidental revert and restore the code.

### Case 2: Intentional Revert (Good)

You're deliberately reverting a broken feature:

```
⚠️  WARNING: Regression detected!
📄 src/egregora/experimental/feature.py matches abc1234 from 3 days ago

Continue? (y/N): y  ← You proceed intentionally
```

**Outcome:** Commit succeeds with your intentional revert.

### Case 3: Jules Creates PR with Regression

Jules creates a PR that accidentally reverts code:

1. GitHub Action runs automatically
2. Detects regression
3. Comments on PR with warning
4. Adds `⚠️ possible-regression` label
5. Fails the check (requires review before merge)

## Configuration

### Adjust Lookback Period

Edit `.pre-commit-config.yaml`:

```yaml
- id: detect-regression
  name: Detect code regressions
  entry: python .github/scripts/detect_regression.py --lookback-days 60
```

### Disable for Specific Files

Edit `.github/scripts/detect_regression.py` and add to skip list:

```python
# Skip non-code files
if any(
    file.endswith(ext)
    for ext in [".md", ".txt", ".json", ".csv", ".lock", ".gitignore", ".yaml"]
):
    continue
```

## Troubleshooting

### False Positives

**Q:** The detector flags a file that's not actually a regression

**A:** This can happen if:
- You're legitimately re-implementing something the same way
- The file is generated code
- You're merging an old branch

**Solution:** Review and confirm it's not a regression, then proceed with `y`

### Performance

**Q:** Pre-commit is slow

**A:** The detector only checks recent history (30 days by default). If still slow:
- Reduce lookback period: `--lookback-days 7`
- Disable for large commits: `git commit --no-verify`

### Not Catching Regressions

**Q:** A regression wasn't detected

**A:** Check:
- File type might be in skip list
- Commit was older than lookback period
- Content changed slightly (not exact match)

## Technical Details

### How File Hashing Works

```python
# Git's object hash (SHA-1)
git hash-object file.py
# → 8baef1b4abc478178b004d62031cf7fe6db6f903

# Same file, different commit? Same hash!
```

The detector compares hashes, so even a single character difference means no match.

### Why Exact Matches Only?

We only flag **exact** content matches because:
- ✅ High precision: No false positives from similar code
- ✅ Fast comparison: Hash lookups are O(1)
- ❌ Won't catch: Partial reverts or line-by-line reversions

This is intentional - we want to catch the most obvious regressions without noise.

## Contributing

To improve the detector:

1. Edit `.github/scripts/detect_regression.py`
2. Test locally: `python .github/scripts/detect_regression.py`
3. Test in pre-commit: `pre-commit run detect-regression`
4. Submit PR with your improvements

## Related

- [Pre-commit framework docs](https://pre-commit.com/)
- [Git hash-object docs](https://git-scm.com/docs/git-hash-object)
- Original issue: PR #2691 regression incident

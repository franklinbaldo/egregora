# Gemini PR Review Prompt Improvement Analysis

## Executive Summary

The current Gemini PR review prompt is comprehensive but suffers from verbosity, conflicting instructions, and missing egregora-specific checks. The improved version reduces token usage by ~40% while adding critical missing functionality.

**Key Metrics:**
- **Token reduction:** ~3000 tokens → ~1800 tokens (saves ~40%)
- **New checks added:** 6 egregora-specific pattern checks
- **Clarity improvements:** Resolved 3 conflicting instruction sets
- **Merge decision:** Added clear criteria and risk level definitions

---

## Detailed Comparison

### 1. **Token Efficiency** ⭐ HIGH IMPACT

**Problem:**
- Current prompt: ~270 lines, ~3000 tokens
- Repetitive explanations (e.g., "understand first" appears 6+ times)
- Verbose examples that waste space

**Solution:**
- Consolidated repetitive sections
- Condensed examples while keeping key lessons
- Removed redundant explanations
- **Result:** ~150 lines, ~1800 tokens (40% reduction)

**Expected Improvement:**
- More space for code diffs in context window
- Faster processing (fewer input tokens)
- Lower API costs per review

---

### 2. **Egregora-Specific Pattern Checks** ⭐ HIGH IMPACT

**Problem:**
Current prompt says "check egregora patterns" but doesn't specify what to check. It references CLAUDE.md but doesn't extract the critical rules.

**Solution:**
Added explicit checklist in "Egregora Pattern Compliance" section:

```markdown
## ✅ Egregora Patterns

- [ ] No banned imports (`pandas`, `pyarrow` - use `ibis` instead)
- [ ] Type annotations present on all new functions
- [ ] Absolute imports only (no relative imports)
- [ ] V2/V3 compatibility maintained
- [ ] Custom exceptions inherit from `EgregoraError`
- [ ] Tests added/updated for new code
```

**Expected Improvement:**
- Catch banned `pandas`/`pyarrow` imports (currently missed)
- Enforce type annotations (critical for mypy strict mode)
- Flag relative imports (banned by ruff configuration)
- Ensure V2/V3 Document class compatibility
- Require tests for new features/bug fixes

---

### 3. **Merge Decision Criteria** ⭐ HIGH IMPACT

**Problem:**
- Current prompt doesn't define when to set `merge: false`
- `merge_risk` levels (low/medium/high) undefined
- Reviewers lack guidance on blocking vs. non-blocking issues

**Solution:**
Added explicit merge decision criteria:

```markdown
## Merge Decision Criteria

Set `merge: false` if ANY:
- Critical bugs (logic errors breaking functionality)
- Security/privacy violations
- Pattern violations (banned imports, missing type hints)
- Missing tests for new features/bug fixes
- Undocumented breaking changes

Set `merge: true` if:
- No critical issues OR only minor/style issues

### Merge Risk Levels
- **low:** Documentation, tests, minor refactors
- **medium:** New features, dependency updates, significant refactors
- **high:** Breaking changes, security-sensitive code, data migrations
```

**Expected Improvement:**
- Consistent merge gate decisions
- Clear risk assessment for auto-merge workflows
- Reduced false positives (blocking PRs unnecessarily)
- Reduced false negatives (approving problematic PRs)

---

### 4. **Test Coverage Guidance** ⭐ MEDIUM IMPACT

**Problem:**
Current prompt mentions "test coverage" in passing but doesn't check:
- Are there tests for new code?
- Do tests cover edge cases?
- Are assertions meaningful?

**Solution:**
Added explicit test quality checks:

```markdown
**Test Quality:**
- [ ] Do tests cover the actual behavior (not just happy paths)?
- [ ] Test names clearly describe what they're testing?
- [ ] Meaningful assertions (not just `assert result is not None`)?
```

**Expected Improvement:**
- Flag missing tests for new features
- Encourage edge case testing
- Improve test assertion quality
- Reduce "write-only tests" (tests that don't validate behavior)

---

### 5. **Resolved Conflicting Instructions** ⭐ MEDIUM IMPACT

**Problem:**
Current prompt has contradictions:
- "You MUST complete Phase 1 before Phase 2" (line 19)
- "Skip Phase 1 if intent is obvious" (line 73)

**Solution:**
Clarified with single statement:

```markdown
Skip Phase 1 only for trivial changes where intent is immediately obvious
(e.g., fixing a typo, updating a version number).
```

**Expected Improvement:**
- Reduced confusion about when to skip Phase 1
- More consistent review structure
- Less wasted tokens on Phase 1 for trivial PRs

---

### 6. **Clearer Output Format** ⭐ MEDIUM IMPACT

**Problem:**
Current prompt has TWO output format sections (lines 194-256 and 257-270):
1. Markdown template
2. JSON schema

The JSON section says "Return ONLY valid JSON (no markdown)" which contradicts the markdown template.

**Solution:**
- Single unified output format section
- Clarified that `review_comment` field contains markdown
- Removed ambiguity about JSON vs. markdown

**Expected Improvement:**
- Better JSON parsing success rate
- Consistent review formatting
- Fewer workflow failures due to malformed output

---

### 7. **AI-Generated Code Detection** ⭐ LOW IMPACT

**Problem:**
With Jules and other AI agents contributing code, reviews should check for AI-specific issues:
- Over-engineering
- Unnecessary abstractions
- Verbose docstrings/comments

**Solution:**
Added to quality checklist:

```markdown
- [ ] Over-engineered? (Premature abstractions, unnecessary complexity)
- [ ] AI-generated artifacts? (Excessive docstrings, verbose comments)
```

**Expected Improvement:**
- Catch over-engineered AI contributions
- Maintain code simplicity
- Reduce unnecessary abstractions

---

### 8. **Removed Irrelevant Content** ⭐ LOW IMPACT

**Problem:**
Current prompt includes:
- "Take 2-5 minutes" time guidance (line 21) - LLMs don't experience time
- Runner context about model fallback order (lines 11-13) - not relevant to review logic
- Word budgets (lines 251-255) - arbitrary and limiting

**Solution:**
Removed these sections entirely.

**Expected Improvement:**
- Cleaner, more focused prompt
- No confusion about time-based expectations
- Flexibility in review length based on actual complexity

---

## Side-by-Side Example

### Current Prompt (excerpt)

```markdown
### Phase 1: Understanding (REQUIRED FIRST - take 2-5 minutes)

Your first job is **understanding, not judging**. Ask yourself:

1. **What changed?** (Read the diff first)
   - Which files? What type of change? (feature/fix/refactor/docs/config)
   - What do imports, function names, and structure tell you?
   - What will this code DO when executed?

2. **What was the author trying to accomplish?**
   - Read PR title/description and commits (they're often vague or missing - that's OK)
   - What's the strongest interpretation of the code's intent?
   - What constraints might justify this approach?

3. **Does stated intent match actual changes?**
   - If YES: Great, you understand the goal
   - If NO/PARTIAL: Infer intent from code (code is ground truth)
   - If description is empty: No problem, infer from code

4. **Steel-man the approach**
   - What's a legitimate reason for doing it this way?
   - What might the author know that isn't obvious?
   - Assume competence unless proven otherwise

**Phase 1 Output:** Write a 3-5 sentence summary of what this PR does and why.
```

### Improved Prompt (excerpt)

```markdown
## Phase 1: Understanding

1. **Analyze the diff** - What files changed? What patterns emerge?
2. **Infer intent** - What is this PR trying to accomplish? (PR description may be vague/missing—use code as ground truth)
3. **Steel-man the approach** - What's a valid reason for this implementation? Assume competence.
4. **Define success criteria** - What does "working correctly" mean for this PR?

**Output:** 2-4 sentences summarizing what the PR does and why.

Skip Phase 1 only for trivial changes where intent is immediately obvious.
```

**Improvement:**
- 15 lines → 7 lines (53% reduction)
- Same conceptual coverage
- More actionable, less philosophical

---

## Expected Quality Improvements

### Before (Current Prompt Issues)

**Example Review Miss:**
```python
# PR adds pandas import
import pandas as pd

def process_data(df):
    return df.groupby('user').mean()
```

**Current Review:** Might not flag the banned `pandas` import because it's not explicitly in the checklist.

**Improved Review:** Will flag it immediately:
```markdown
## 🔴 Critical Issues

**data_processor.py:1** - 🔴 Banned import detected. Using `pandas` is prohibited—use `ibis-framework` instead per CLAUDE.md. Replace with:
```python
import ibis
table = ibis.read_parquet('data.parquet')
result = table.group_by('user').aggregate(ibis._.mean())
```
```

---

### Before (Current Prompt Issues)

**Example Review Miss:**
```python
# PR adds new feature without tests
def calculate_user_score(messages: list[Message]) -> float:
    # Complex logic...
    return score
```

**Current Review:** Might not flag missing tests because checklist doesn't explicitly require it.

**Improved Review:** Will flag it:
```markdown
## 🔴 Critical Issues

**scorer.py:45** - 🔴 New feature `calculate_user_score` has no tests. Add tests covering:
- Empty message list
- Single message
- Multiple messages with different scores
- Edge case: all messages have zero engagement
```

---

### Before (Current Prompt Issues)

**Example Review Inconsistency:**
```python
# PR has minor style issue
def process(data):  # Missing type annotation
    return data.upper()
```

**Current Review:** Might block merge due to missing type annotation OR might approve it depending on interpretation.

**Improved Review:** Clear merge decision:
```markdown
## 🟡 Quality Concerns

**utils.py:12** - 🟡 Missing type annotation on `process` function. Add: `def process(data: str) -> str:`

## 📊 Verdict

**Recommendation:** MERGE WITH MINOR FIXES ⚠️
**merge:** true (minor issue, doesn't block functionality)
**merge_risk:** low
**Top priority action:** Add type annotation in follow-up PR or before merge
```

---

## Migration Plan

### Phase 1: Testing (Week 1)
1. **Run A/B test**: Compare reviews from current vs. improved prompt on same PRs
2. **Metrics to track**:
   - Review quality (subjective evaluation by team)
   - False positive rate (blocking good PRs)
   - False negative rate (approving problematic PRs)
   - Token usage reduction
   - Review consistency

### Phase 2: Gradual Rollout (Week 2)
1. **Deploy to test PRs**: Use improved prompt on non-critical PRs
2. **Collect feedback**: Ask team if reviews are better/worse
3. **Iterate**: Adjust based on feedback

### Phase 3: Full Deployment (Week 3)
1. **Replace current prompt**: Switch `.github/prompts/pr-review-prompt.md`
2. **Monitor**: Watch for regression in review quality
3. **Document**: Update GEMINI_PR_REVIEW.md with new capabilities

---

## Risk Analysis

### Low Risk
- Token efficiency improvements (can't make reviews worse)
- Clarifying conflicting instructions (removes ambiguity)
- Adding explicit checklists (makes requirements clearer)

### Medium Risk
- Merge criteria changes might alter auto-merge behavior
- **Mitigation:** Test on historical PRs to validate decisions
- More strict egregora pattern checks might block more PRs
- **Mitigation:** Ensure checks align with actual project standards

### High Risk
- None identified

---

## Success Criteria

The improved prompt is successful if:

1. **Token efficiency:** ≥30% reduction in prompt tokens (target: 40% achieved ✅)
2. **Pattern compliance:** ≥90% catch rate for banned imports and missing type annotations
3. **Test coverage:** ≥80% of new features flagged if missing tests
4. **Merge decisions:** ≥95% agreement with human reviewer decisions
5. **Review consistency:** ≤10% variance in reviews of same PR
6. **Team satisfaction:** ≥4/5 average rating from team on review quality

---

## Appendix: Full Diff Summary

| Category | Current | Improved | Change |
|----------|---------|----------|--------|
| **Lines** | 270 | 150 | -44% |
| **Tokens** | ~3000 | ~1800 | -40% |
| **Egregora checks** | 0 explicit | 6 explicit | +600% |
| **Merge criteria** | Vague | Explicit | ✅ |
| **Test guidance** | Minimal | Comprehensive | ✅ |
| **Output format** | Duplicate | Unified | ✅ |
| **Conflicting rules** | 3 | 0 | ✅ |

---

## Recommended Next Steps

1. **Immediate:** Review this analysis with team for feedback
2. **Week 1:** Run A/B test on 10-20 recent PRs
3. **Week 2:** Deploy to non-critical PRs with manual oversight
4. **Week 3:** Full deployment if metrics meet success criteria
5. **Ongoing:** Iterate based on team feedback and review quality metrics

---

**Document Author:** Claude Code Analysis
**Date:** 2026-01-02
**Status:** Draft - Awaiting Team Review

---
title: "🧑‍🌾 Historical Archive"
date: 2025-12-23
author: "Shepherd"
emoji: "🧑‍🌾"
type: journal
---

# Shepherd's Journal - Coverage Improvement Learnings

This journal tracks critical learnings from coverage improvement sessions.

## Format
```
## YYYY-MM-DD - Coverage: XX% → YY% (+Z.Z%)
**Files Tested:** [module names]
**Key Behaviors:** [What behaviors were tested?]
**Obstacles:** [What made testing difficult?]
**Solutions:** [How did you overcome them?]
```

---

## 2025-12-23 - Coverage: 35% → 39% (Initial Baseline)
**Files Tested:** Initial baseline established
**Key Behaviors:** N/A - baseline measurement
**Obstacles:**
- Coverage was measured with statement coverage only (43.91%)
- CI uses branch coverage (--cov-branch) which is stricter (39.24%)
- Mismatch caused CI failures
**Solutions:**
- Set threshold to 39% to match branch coverage
- Added --cov-branch to pre-commit configuration
- Documented difference between statement vs branch coverage

**Note:** Branch coverage requires testing BOTH branches of if/else statements, not just executing the if statement. This is why it's lower than statement coverage.

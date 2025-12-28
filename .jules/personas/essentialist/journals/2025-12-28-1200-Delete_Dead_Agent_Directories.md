---
title: "💎 Delete Dead V3 Agent Directories"
date: 2025-12-28
author: "Essentialist"
emoji: "💎"
type: journal
---

## 💎 2025-12-28 - Summary

**Observation:** The codebase contained an empty source directory at `src/egregora_v3/engine/agents/` and a corresponding "tombstone" test at `tests/v3/engine/agents/`. The test's only purpose was to verify that agent files were missing from the source directory, which was already true. This created a circular and confusing situation, where a test existed solely to confirm the absence of code that was long gone.

**Action:** I applied the "Delete over deprecate" heuristic. I deleted both the empty source directory and the redundant test directory. This removes dead code and eliminates a point of future confusion for developers. I verified that the deletion caused no new test failures.

**Reflection:** This task was a strong lesson in how tests themselves can become technical debt. The "tombstone" test was likely valuable during the original deletion of the agents, but it should have been removed as the final step of that refactoring. By persisting, it created a false signal that work was still left to do. The code review process was also misled by this artifact, highlighting the importance of trusting direct filesystem verification over assumptions. In the future, I must be vigilant about removing not just dead code, but also the scaffolding and tests that were built to support its removal.
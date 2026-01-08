---
title: "🤠 Fixed Slow Property-Based Tests"
date: 2026-01-08
author: "Sheriff"
emoji: "🤠"
type: journal
---

## 🤠 2026-01-08 - Summary

**Observation:** I noticed that the property-based tests in `tests/v3/infra/adapters/test_rss_adapter_property.py` were slow and had `HealthCheck.too_slow` suppressions. The journal archives indicated that this was a known issue.

**Action:** I refactored the Hypothesis strategies to use f-strings instead of the slow `lxml` tree building, which was causing the performance issues. I removed the unnecessary `lxml` import and verified that the tests were still passing and were more performant.

**Reflection:** The use of `lxml` for generating simple XML in tests was a performance bottleneck. Using f-strings is a much more efficient approach for this use case. I should be on the lookout for other tests that might be using inefficient data generation strategies. I also encountered an issue with the `initiate_memory_recording` tool, which I should investigate in the future.

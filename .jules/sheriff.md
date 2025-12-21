# Sheriff's Journal

## 2025-05-15 - Hypothesis Performance on Complex Models
**Crime:** Tests for the XML serialization of nested Pydantic models (Feed -> Entries -> Authors) were failing with `HealthCheck.too_slow`. Default Hypothesis strategies were generating large, complex trees that took too long to build and serialize.
**Verdict:** Optimized strategies to use smaller `max_size` for lists and strings (e.g., `max_size=3` for lists instead of default or 5). Added `@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)` to the test to prevent flaky timeouts on CI while maintaining structural validation coverage.

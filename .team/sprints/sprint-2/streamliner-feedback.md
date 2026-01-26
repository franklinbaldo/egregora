# Feedback: Streamliner - Sprint 2

**Author:** Streamliner 🌊
**Date:** 2026-01-26

## General Observations
- **Template Inconsistency:** The `TEMPLATE-plan.md` is in Portuguese, which has led to mixed languages in the plans (Visionary used Portuguese, others English). We should standardize on English for consistency across the codebase and documentation.

## Specific Feedback

### Simplifier 📉
- **Plan:** Extract ETL logic from `write.py`.
- **Feedback:** This is a crucial refactor. Once the ETL logic is extracted into `src/egregora/orchestration/pipelines/etl/`, I can more easily apply vectorized optimizations to the data loading and transformation steps. Let's coordinate on the interface for the extracted pipelines to ensure they remain Ibis-compatible/declarative.

### Lore 📚
- **Plan:** Document "Batch Era" and analyze `runner.py`.
- **Feedback:** Preserving the history of the imperative approach is valuable. It highlights *why* we are moving to declarative patterns. Your analysis might uncover edge cases in `runner.py` that my optimizations need to respect.

### Visionary 🔭
- **Plan:** Code Reference Detection (RFC 027).
- **Feedback:** The plan is in Portuguese. Please translate to English for team alignment. Regarding the technical content: Regex + Git CLI for "Context Layer" resolution sounds potentially slow (imperative). Consider if we can index the git history into a DuckDB table (as hinted in your plan) to allow for SQL-based joins between Chat Messages and Code References. This would be much faster than shelling out to `git` for every message.

### Sentinel 🛡️
- **Plan:** Secure Config and ADRs.
- **Feedback:** No specific data processing concerns. Security looks solid.

# ADR-006: Adopt a DataFrame-Native Content Pipeline

## Status
Accepted

## Context
The previous newsletter pipeline converted WhatsApp exports between Polars DataFrames and plain-text transcripts several times. This increased latency, duplicated business rules, and made media/link enrichment harder to reason about. The CODE_ANALYSIS report flagged the split between the DataFrame-oriented parser/merger modules and the legacy text pipeline as the primary architectural risk.

## Decision
Unify the hot path on Polars:

- Enforce a canonical `MESSAGE_SCHEMA` when parsing and caching WhatsApp exports.
- Render transcripts directly from DataFrames via `render_transcript`, removing the `extract_transcript` shim.
- Expose DataFrame-native enrichment and media helpers that rely on vectorised expressions.
- Drive orchestration from `UnifiedProcessor` using Polars frames, with a feature flag (`use_dataframe_pipeline`/`EGREGORA_USE_DF_PIPELINE`) to fall back to the legacy behaviour if necessary.

## Consequences
- Substantial reduction in DataFrame ↔ text conversions and duplicated logic.
- Easier to extend enrichment/media extraction because inputs keep structural metadata (author, timestamps, tagged lines).
- Legacy text-only consumers can still opt out temporarily via the feature flag, but the new path is the default.
- Additional schema validation ensures downstream modules see consistent datatypes and timezone information.

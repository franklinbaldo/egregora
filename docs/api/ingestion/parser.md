# Ingestion Parser

The ingestion parser converts raw exports into the intermediate representation (IR) used by downstream stages.

## Responsibilities
- Validate required columns and timestamps before the privacy gate runs.
- Normalize message metadata into the canonical schema used by enrichment and RAG.
- Surface meaningful errors when adapters emit malformed records.

## Status
This document will be expanded with code samples and adapter-specific notes as the pipeline stabilizes.

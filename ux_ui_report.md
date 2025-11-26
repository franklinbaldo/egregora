
# Egregora UX/UI & Debugging Report

## Overview
This report documents the observations, errors encountered, and fixes applied during the attempt to generate a blog from a WhatsApp export using `egregora`.

## Errors Encountered & Fixes

### 1. DuckDB Array Type Mapping (`ParserException`)
- **Issue:** The `_ibis_to_duckdb_type` function was generating invalid SQL for array types (e.g., `ARRAY<DOUBLE>`), which caused a `ParserException` in DuckDB.
- **Fix:** Updated `src/egregora/database/ir_schema.py` to use the correct DuckDB array syntax (`DOUBLE PRECISION[]`, `VARCHAR[]`).
- **Status:** Resolved.

### 2. DuckDB File Lock (`IOException`)
- **Issue:** Persistent `IOException` due to file locks on `pipeline.duckdb`.
- **Fix:** Manually killed the locking process and deleted the `.egregora` directory to reset the database state.
- **Status:** Resolved (by cleanup).

### 3. VectorStore Attribute Error (`AttributeError`)
- **Issue:** `VectorStore._candidate_vss_functions` accessed `self._vss_function` before it was initialized, causing a crash when VSS search failed.
- **Fix:** Updated `src/egregora/agents/shared/rag/store.py` to check for attribute existence using `hasattr`.
- **Status:** Resolved.

### 4. VSS Query Type Mismatch (`Invalid Input Error`)
- **Issue:** `vss_match` failed because the query vector was cast to `FLOAT[]` (32-bit) while the table column was `DOUBLE PRECISION[]` (64-bit).
- **Fix:** Updated `src/egregora/agents/shared/rag/store.py` to cast query vectors to `DOUBLE[]`.
- **Status:** Resolved.

### 5. Unhandled Google API Errors (`ServerError`)
- **Issue:** The `tenacity` retry logic in `src/egregora/utils/batch.py` was not catching `google.genai.errors.ServerError` (500) because it was only configured for `google.api_core.exceptions`.
- **Fix:** Updated `src/egregora/utils/batch.py` to import and include `google.genai.errors.ServerError` in the retryable exceptions list.
- **Status:** Resolved (retry logic updated).

### 6. Segmentation Fault (Exit Code 139)
- **Issue:** The generation process crashed with a Segmentation Fault during the writing phase, likely due to memory issues or internal library faults (possibly DuckDB or Google GenAI SDK) under load.
- **Status:** Unresolved. This prevented the final generation of blog posts.

## UX/UI Observations

- **Error Reporting:** The CLI error reporting is generally good but can be verbose. The stack traces for internal library errors (like DuckDB SQL errors) could be wrapped in more user-friendly messages.
- **Progress Feedback:** The progress bars and logging are helpful, but a "dry run" or "validation" mode would be useful to catch configuration/schema issues before starting the expensive generation process.
- **Resumability:** The pipeline seems to lack robust checkpointing/resumability. A crash requires a full restart (often with manual cleanup of the output directory), which is frustrating for long-running tasks.
- **Dependency Management:** The mix of `google.genai` (v1 beta) and `google.generativeai` (older SDK) or `google.api_core` seems to cause confusion in exception handling. Standardizing on one SDK version would improve stability.

## Recommendations
1.  **Implement Checkpointing:** Allow the pipeline to resume from the last successfully processed window.
2.  **Standardize SDK Usage:** Migrate fully to `google.genai` and ensure all exception handling aligns with it.
3.  **Memory Management:** Investigate memory usage during the writer phase, especially when handling large contexts or many concurrent requests, to prevent segfaults.
4.  **Dry Run Mode:** Add a `--dry-run` flag to validate schema, API keys, and basic connectivity without running the full generation.

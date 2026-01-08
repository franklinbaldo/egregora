# 6. Journal-Based Execution Log

Date: 2025-05-23

## Status

Accepted

## Context

The Egregora pipeline needs to track which "windows" of messages have already been processed to avoid duplicate work and duplicate posts.

Previously, this was handled by a `checkpoint.json` file in the `.egregora/` directory, which tracked the timestamp of the last processed message.

**Problems with file-based checkpoints:**
1.  **State Drift:** The file is local and mutable. If the database (DuckDB) and the file get out of sync (e.g., DB deleted but checkpoint remains), the pipeline silently skips data.
2.  **Granularity:** It only tracked a simple timestamp (`last_processed_timestamp`). It could not handle gaps or re-processing of specific windows.
3.  **Atomicity:** The checkpoint was updated separately from the content insertion, leading to potential inconsistencies if the process crashed between writing posts and saving the checkpoint.

## Decision

We will use the **Agent's Journal** (`DocumentType.JOURNAL`) as the authoritative record of execution.

1.  **Unified Storage:** Execution logs are just `Document` objects stored in the same `documents` table as Posts and Profiles.
2.  **1:1 Correspondence:** Every processed window produces exactly one `JOURNAL` document.
3.  **Deduplication Key:** The system checks for the existence of a `JOURNAL` covering the exact time range (`window_start`, `window_end`).
4.  **Logic:** Before processing a window, the pipeline queries the `documents` table to see if a Journal with matching start/end timestamps already exists. If found, the window is skipped.

## Consequences

**Positive:**
*   **Atomic:** The "flag" that a window is done is written in the same transaction/operation as the content itself.
*   **Robust:** Deleting the database resets the state automatically. No stale files.
*   **Audit Trail:** The Journal contains the "why" (Agent's reasoning) and the "what" (metadata), serving double duty as a debug log and a state lock.

**Negative:**
*   **Storage Size:** Storing full journal text for every window increases database size (though negligible for text).
*   **Query Overhead:** Must query the database/metadata for existing journals.

## Future Enhancements

*   **Signature-Based Invalidation:** In the future, we may include a `window_signature` (hash of data + prompt + model) in the deduplication logic. This would allow automatic re-processing if the prompt or model logic changes, effectively versioning the pipeline execution. For the initial implementation, simple time-based deduplication is sufficient.

## Implementation Details

*   **Type:** `DocumentType.JOURNAL`
*   **Metadata Fields (in `internal_metadata`):**
    *   `window_start` (ISO8601)
    *   `window_end` (ISO8601)

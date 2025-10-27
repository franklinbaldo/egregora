# annotate_conversation Tool Implementation Plan

## Overview
Provide a planning document for introducing a new tool `annotate_conversation(msg_id, my_commentary)` that the writer agent can invoke to store annotations tied to conversation chunks. The stored annotations are invisible to readers, persist in a database, and will be re-injected whenever the same chunk of the conversation is revisited in chronological order. The author field for the annotation should be `egregora`. On subsequent passes, the agent may add new annotations and can use previous annotations as contextual memory.

## Goals
- Allow the writer agent to call `annotate_conversation` while processing a conversation.
- Persist commentary keyed by `msg_id`, `author`, and chronological position so that future iterations receive the stored annotations automatically.
- Provide a safe, debuggable mechanism for the agent to iteratively extend its annotations.

## Requirements
1. **Tool signature**: `annotate_conversation(msg_id: str, my_commentary: str) -> None`.
2. **Annotation semantics**:
   - Each annotation is linked to a specific conversation message `msg_id`.
   - The annotation text is treated as private memory; not visible to end users.
   - When a conversation chunk is revisited, any prior annotations for that chunk must be loaded and injected as context authored by `egregora`.
   - The tool may be invoked multiple times for the same `msg_id`; new annotations should append without overwriting previous entries.
3. **Persistence**:
   - Annotations are stored in a database layer (initially simple key-value or SQLite for prototyping).
   - Stored data must include `msg_id`, `author` (always `egregora`), `commentary`, timestamp, and an optional `parent_annotation_id` to support chaining/patents of memory.
   - Database schema must support efficient retrieval by `msg_id` sorted by chronological insertion.
4. **Replay logic**:
   - When reconstructing context for a conversation chunk, fetch annotations ordered by timestamp and inject them into the prompt sequence immediately after the original message.
   - Ensure duplicate injections are avoided across multiple passes within the same session.
5. **Safety & privacy**:
   - Guard against unsafe content by reusing existing moderation or sanitization utilities before persisting annotations.
   - Ensure annotations remain inaccessible to external consumers unless explicitly surfaced for debugging with appropriate permissions.
6. **Extensibility**:
   - Design storage and tool layers to accommodate additional metadata (e.g., tags, confidence scores) without schema-breaking changes.

## Implementation Plan
1. **Schema design**
   - Add a new `annotations` table with fields (`id`, `msg_id`, `author`, `commentary`, `created_at`, `parent_annotation_id`).
   - Create necessary indices on `msg_id` and `created_at` for fast retrieval.
2. **Database integration**
   - Extend the persistence module to expose CRUD functions: `save_annotation`, `list_annotations_for_message`, and optional `link_parent_annotation`.
   - Implement migrations if using a managed database or include schema bootstrap logic for local storage.
3. **Tool registration**
   - Define the `annotate_conversation` tool handler that validates inputs, invokes moderation, and persists the annotation using `save_annotation`.
   - Ensure the tool sets the `author` field to `egregora` automatically.
4. **Conversation replay hooks**
   - Update the conversation reconstruction pipeline so that, when loading a message by `msg_id`, it calls `list_annotations_for_message` and injects the results into the prompt buffer as messages authored by `egregora`.
   - Handle chronological insertion to maintain ordering relative to original conversation flow.
5. **Iterative annotation support**
   - Allow annotations to reference previous ones by storing a `parent_annotation_id` when the agent builds upon its prior memory.
   - Provide helper utilities that return the last annotation ID for a given `msg_id` to simplify linking.
6. **Testing strategy**
   - Unit tests for persistence helpers to confirm append-only behavior and chronological ordering.
   - Integration tests that simulate a conversation pass, saving annotations, and verifying they reappear on subsequent runs.
   - Regression tests ensuring annotations remain hidden from user-facing transcripts.
7. **Documentation & observability**
   - Update developer documentation describing the new tool usage and replay behavior.
   - Add logging around annotation creation and retrieval for troubleshooting.

## Open Questions
- Should annotations be scoped per user/session or global across all instances? Clarify retention policy and cleanup mechanisms.
- Determine storage quotas or pruning strategies to prevent unbounded growth.
- Confirm whether annotations require encryption at rest.

## Milestones
1. Prototype schema and persistence layer.
2. Implement tool handler and register with the writer agent runtime.
3. Integrate replay logic and verify end-to-end behavior.
4. Add automated tests and documentation updates.
5. Conduct code review and deploy.

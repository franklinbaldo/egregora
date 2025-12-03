# Egregora V3 Reflection: Privacy & Architecture

## 1. Privacy Strategy Reflection

### The Concern
The V3 Plan calls for an "Adapter-Driven Privacy" model with a strong emphasis on anonymizing data *before* it enters the system (Phase 2.3). The user is concerned this might repeat errors from V2, potentially "over-focusing" on privacy at the expense of simplicity or functionality.

### V2 Implementation Analysis
V2 (`src/egregora/privacy/anonymizer.py` and `src/egregora/input_adapters/whatsapp/adapter.py`) implemented a complex privacy layer:
*   **Mandatory Checks**: The `anonymize_table` function validates columns (`author_raw`, `author_uuid`) and raises errors if missing.
*   **Granular Config**: `AdapterPrivacyConfig` supports different strategies (UUID_MAPPING, FULL_REDACTION) per adapter.
*   **Regex Sanitization**: Complex regex logic (`_sanitize_mentions`) runs inside UDFs to scrub mentions from message bodies.
*   **Complexity**: The `WhatsAppAdapter` has significant logic dedicated to `_apply_privacy`, which couples the adapter tightly to the privacy implementation.

### V3 Assessment
The proposed V3 plan (Adapter-Driven Privacy) essentially says: "Do this cleanup at the edge, so the Core doesn't know about PII."
*   **Risk**: If we port the V2 logic verbatim, we inherit the complexity (regexes, UDFs, configuration overhead).
*   **Benefit**: The Core `Document` and `FeedItem` become truly safe. We don't need PII checks in the Agent or Output layers because we *guarantee* clean data at ingress.
*   **Verdict**: The *intent* is correct (separation of concerns), but the *implementation* should be simplified. V2's "Mandatory Validation" inside the storage layer was the real pain point. Moving it to the Adapter is an improvement, provided the Adapter implementation itself is kept simple (e.g., streaming transformation rather than complex dataframe mutations).

### Recommendation
**Downgrade Strictness**: Do not make privacy "Mandatory" in a way that blocks valid data.
*   Allow the pipeline to run in "Trusted Mode" (no anonymization) for personal use cases.
*   Treat Privacy as a *Transformer* step in the pipeline, not a hard gate in the Adapter. This allows `FeedItems` to be ingested raw and anonymized later if desired, or anonymized on the fly.
*   **Plan Update**: Change "Adapter-Driven Privacy" (hard requirement) to "Pipeline Transformation" (composable step).

## 2. UUIDv5 vs UrlConvention Reflection

### The Concern
V3 uses UUIDv5 (SHA-256 hash of content) for `Document` IDs. The user questions if this is an overuse or complexity trap and suggests exploring `UrlConvention` (from V2) as a replacement.

### Analysis
*   **UUIDv5 (Identity = Content)**: "I am what I contain." If content changes, ID changes.
    *   *Pros*: Perfect deduplication. Automatic cache invalidation. No collision risk.
    *   *Cons*: Edits break external links. Opaque (unreadable).
*   **UrlConvention (Identity = Location)**: "I am where I live." (e.g., `posts/2023/my-post`)
    *   *Pros*: Human-readable. Stable under edits (if slug is preserved). SEO-friendly.
    *   *Cons*: Deduplication is manual. Renaming (moving) breaks identity. Requires unique constraint management (collisions).

### Strategic Pivot: Hybrid Identity
The user suggests "UrlConvention" was a great addition. Indeed, for *Public* documents (Posts, Profiles), the URL *is* the identity that matters to the world.
Using UUIDv5 for everything treats a human-edited Post the same as a machine-generated Vector Chunk. This is likely the "overuse" error.

**Proposed Change:**
1.  **Internal Artifacts (Chunks, Embeddings, Intermediate)**: Keep `UUIDv5`. We need strict deduplication here.
2.  **Public Documents (Posts, Profiles)**: Shift strict identity to `UrlConvention` (Semantic ID).
    *   The `Document.id` for a Post should ideally be its *Canonical URL path* (or a UUIDv5 of that path, which makes it stable).
    *   Alternatively, `Document` maintains a `uuid` field (random or hash) but the system primary key becomes the `slug`.

**Refined Approach**:
Instead of replacing UUIDv5 entirely, we replace the *primary reliance* on it for user-facing content.
*   **Document ID**: Still useful for database PKs.
*   **UrlConvention**: Becomes the *authoritative* source of truth for file paths and inter-document linking.
*   **Refinement**: `UrlConvention` should be lifted from an "Output" detail to a "Core" concept for these document types.

### Recommendation
*   **Adopt UrlConvention as Primary Identity for Posts**: The "ID" of a post in the user's mind is its filename/slug.
*   **Hybrid Strategy**: Use `UUIDv5` for *immutable* data (FeedItems, Media Blobs). Use `Semantic IDs` (Slugs/Paths) for *mutable* content (Posts, Profiles).
*   **Action**: Add an evaluation task to Phase 1.5 to "Prototype UrlConvention-based Identity for Posts".

## 3. PipelineContext Reflection

*   **Current Plan**: Added `PipelineContext` to L1.
*   **Reflection**: This is standard best practice for avoiding global state. It is not over-engineering; it is hygiene.
*   **Verdict**: Keep.

## 4. Summary of Plan Adjustments

1.  **Privacy**: Shift from "Adapter Responsibility" to "Optional Pipeline Step".
2.  **IDs**: Differentiate between **Immutable** (Chat Logs, Media) and **Mutable** (Posts) identity.
    *   Immutable -> UUIDv5 (Content Addressed)
    *   Mutable -> Semantic ID (UrlConvention / Slug)
    *   Update plan to explicitly explore this hybrid model.

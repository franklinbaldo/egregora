# RFC: 002 - Structured Data Sidecar
**Status:** Actionable Proposal
**Date:** 2024-07-29
**Disruption Level:** Low - Fast Path

## 1. The Vision
To accelerate the **Egregora Symbiote** vision, we need to begin extracting structured data from conversations *now*. This RFC proposes a simple, non-disruptive addition to the existing V2 pipeline: alongside each generated Markdown post, the Writer agent will also save a `post.json` file. This "sidecar" file will contain a structured representation of the post's content, including identified entities (people, projects), key decisions, action items, and open questions. This creates an immediate, machine-readable dataset that can be used for future analysis, API development, or as the initial fuel for the Symbiote's knowledge base.

## 2. The Broken Assumption
This proposal challenges a subtle but important assumption: **that the only valuable output of the pipeline is human-readable Markdown.**
> "We currently assume that the end product is a blog post for a human to read. This prevents us from creating machine-readable artifacts that unlock programmatic access and higher-order intelligence."

By breaking this, we begin treating the output of Egregora not just as a static website, but as a structured data source.

## 3. The First Implementation Path (≤30 days)
1.  **Update Writer Agent:** Modify the `Writer` agent's Pydantic output model to include a new field, e.g., `structured_data: StructuredPost`, alongside the existing `prose: str`.
2.  **Enhance Prompt:** Update the `writer.jinja` prompt to explicitly ask the LLM to extract entities, decisions, and action items into a specific JSON structure.
3.  **Modify Output Adapter:** In the `MkDocsAdapter`, after writing the `.md` file, add a step to serialize the `structured_data` object to a corresponding `.json` file in the same directory.
4.  **No Breaking Changes:** This approach requires no changes to the existing data schemas, RAG pipeline, or UI. It is a purely additive enhancement.

## 4. The Value Proposition
This is the fastest way to de-risk and accelerate the Symbiote moonshot.
- **Immediate Asset Creation:** We begin building the structured dataset required for the Symbiote *today*, using the existing architecture.
- **Prove the Core Hypothesis:** It will prove whether an LLM can reliably extract structured knowledge from unstructured chat, a critical dependency for the real-time agent.
- **Unlock Near-Term Value:** The generated `.json` files can be immediately used to create richer UIs (e.g., a "Decisions" dashboard) or a simple data API, delivering value long before the full Symbiote is built.

## 5. Success Criteria
- [ ] Within 30 days, the `egregora write` command successfully generates a `.json` file for every `.md` post.
- [ ] The generated JSON contains measurably accurate extractions of at least two of the following: key decisions, action items, or named entities.
- [ ] The addition of this feature does not increase the pipeline's runtime by more than 15%.

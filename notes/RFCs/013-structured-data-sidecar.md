# RFC: Structured Data Sidecar
**Status:** Actionable Proposal
**Date:** 2024-07-25
**Disruption Level:** Low - Fast Path

## 1. The Vision
For every Markdown blog post Egregora generates, it will also generate a corresponding `[post-slug].json` file. This "sidecar" file will contain the structured, machine-readable essence of the post: key entities, topics discussed, decisions made, and participants involved. This provides a clean data layer for future features, starting with the **Egregora Atlas** moonshot.

## 2. The Broken Assumption
This proposal breaks the implicit assumption that the primary output of the Writer Agent must be human-readable prose (Markdown). It introduces the idea that a machine-readable, structured format is an equally important artifact.

## 3. The First Implementation Path (≤30 days)
- **Step 1: Modify Writer Agent Output:** Update the Pydantic output model for the Writer Agent to include a new field, `structured_data`, which will contain a JSON-serializable object with lists of topics, decisions, and people.
- **Step 2: Update Persistence Logic:** In the `MkDocsAdapter`, modify the `publish` method. When it receives a document, it will now perform two write operations: one for the `.md` file as usual, and a second to dump the `structured_data` field to a `.json` file in the same directory.
- **Step 3: (Optional) Enhance Prompt:** Slightly tweak the writer prompt to explicitly ask the LLM to populate these structured fields based on the conversation.

## 4. The Value Proposition
This is the fastest way to de-risk the "Egregora Atlas" vision.
- **Builds the Foundation:** It starts generating the raw data needed for the knowledge graph without requiring a massive architectural change.
- **Unlocks Immediate Value:** The generated JSON files can be used immediately to improve search, create automatic tag clouds, or build an index of key decisions, even before the Atlas UI is built.
- **Incremental & Safe:** It doesn't replace the existing blog output, so it's a purely additive change with no risk of regression for current users.

## 5. Success Criteria
- For every `.md` file in the output `posts/` directory, a corresponding `.json` file exists.
- The JSON file successfully parses and contains keys for `topics`, `decisions`, and `participants`.
- The existing blog generation process is unaffected.

# RFC: Decision Extraction Enrichment
**Status:** Actionable Proposal
**Date:** 2026-01-13
**Disruption Level:** Medium - Fast Path

## 1. The Vision
This proposal introduces a new enrichment skill to the existing pipeline. A "Decision Extraction Agent" will analyze the conversation chunks and extract a structured list of decisions and action items. This structured data will then be injected as a formatted markdown block at the top of each generated blog post, providing an "executive summary" of the post's key outcomes.

## 2. The Broken Assumption
This proposal breaks the assumption that **enrichment is only for adding supplementary metadata (like tags or image descriptions).**

> "We currently assume enrichment adds context *to* the content. This proposal asserts that enrichment can extract the *core value* from the content and present it as a primary feature."

This elevates enrichment from a background task to a headline feature, delivering immediate, high-value structured data to the user without requiring a full architectural shift.

## 3. The First Implementation Path (≤30 days)
- **Develop a new `DecisionExtractionAgent`**: This agent will use Pydantic-AI to define a schema for `Decision` and `ActionItem` objects.
- **Integrate as a new enrichment step**: The new agent will be called within the existing enrichment pipeline.
- **Create a new Jinja macro**: A macro will be created to format the extracted decisions and action items into a clean markdown block (e.g., using blockquotes or a admonition).
- **Update the `writer.jinja` prompt**: The main writer prompt will be updated to include a new section at the top of the post, calling the new macro to render the decisions.

## 4. The Value Proposition
This is the fastest path to delivering the core value of the "Decision Ledger" moonshot. It provides immediate, high-impact value to users by surfacing the most important outcomes of their conversations directly in the blog posts. It's a non-disruptive change that leverages the existing architecture. Most importantly, it allows us to develop and validate the core decision-extraction AI, de-risking the most critical component of the moonshot vision in a fast, iterative loop.

## 5. Success Criteria
- A new `DecisionExtractionAgent` is implemented and tested.
- Blog posts now feature a "Decisions & Actions" section at the top when relevant outcomes are detected.
- The extracted data is accurate and well-formatted.
- The feature is enabled by a configuration flag in `.egregora.toml`.

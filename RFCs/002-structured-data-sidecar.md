# RFC: Structured Data Sidecar
**Status:** Actionable Proposal
**Date:** 2024-07-29
**Disruption Level:** Low - Fast Path

## 1. The Vision
Alongside every generated blog post, the Egregora pipeline will emit a `post.json` file. This "sidecar" file will contain a structured, machine-readable representation of the post's key entities, decisions, and concepts. This immediately makes the output of Egregora queryable and interoperable, providing a new layer of value for power-users and laying the foundational data layer for the [Egregora Symbiote](./001-egregora-symbiote.md).

## 2. The Broken Assumption
This proposal breaks the assumption that the only valuable output of Egregora is human-readable prose. We are currently throwing away valuable structured data that the LLM extracts as an intermediate step.

## 3. The First Implementation Path (≤30 days)
- **Step 1: Modify Writer Prompt:** Update the `writer.jinja` prompt to explicitly ask the LLM to output a JSON block containing key entities (people, projects), decisions made, and open questions.
- **Step 2: Update Writer Agent:** Modify the `Writer` agent to parse this JSON block from the LLM's response.
- **Step 3: New Output Artifact:** The agent will save this JSON content as a new file, e.g., `_index.json`, in the same directory as the generated `index.md` for the post.

## 4. The Value Proposition
This is the fastest path to making Egregora's output useful for other machines. It unlocks immediate use cases like programmatic analysis of decisions or feeding data into other tools, without requiring a massive architectural shift. It is the critical first step towards the Symbiote, de-risking the vision by proving that valuable, structured knowledge can be reliably extracted from unstructured conversations.

## 5. Success Criteria
- [ ] A `post.json` file is generated for every blog post.
- [ ] The JSON file contains valid, structured data for entities, decisions, and concepts.
- [ ] The existing blog generation process is not negatively impacted.

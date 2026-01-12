# RFC: 021 - The `/import` Command
**Status:** Actionable Proposal
**Date:** 2024-07-29
**Disruption Level:** Low - Fast Path

## 1. The Vision
To accelerate **The Egregora Oracle** vision, we must first build the core muscle of ingesting and processing external data. This RFC proposes a simple, user-driven mechanism to do so: a slash command, `/import [URL]`. When a user posts a message with this command, an agent will fetch the content of the URL, summarize it, and—most importantly—ingest the full content into the LanceDB knowledge base. This provides an immediate, high-value utility for users to archive and share external resources while building the foundational pipeline for the proactive Oracle.

## 2. The Broken Assumption
This proposal challenges the assumption that **only chat text can be a source of knowledge.**
> "We currently assume that the RAG knowledge base should only contain embeddings of the group's own conversations. This prevents us from enriching the knowledge base with curated, high-signal external documents."

By breaking this, we begin treating the knowledge base as a library that contains both internal *and* external wisdom.

## 3. The First Implementation Path (≤30 days)
1.  **Modify Parser:** Update the chat parser to recognize messages starting with `/import`.
2.  **Create New Agent:** Develop a simple "Importer" agent responsible for the following workflow:
    a. Take a URL as input.
    b. Use an HTTP client to fetch the page content.
    c. Use a simple extraction library (like `trafilatura` or an LLM call) to get the core text.
    d. Generate a concise summary of the text using an LLM.
    e. Ingest the *full, original text* into LanceDB, with metadata linking to the source URL and the user who imported it.
3.  **Provide Feedback:** The agent posts a message back to the chat confirming the import: "✅ Successfully imported and archived '[Article Title]'. You can now ask me questions about it."

## 4. The Value Proposition
This is the fastest and most direct path to building the core capability of the Oracle moonshot.
- **Immediate Utility:** Users gain a powerful tool for archiving, sharing, and ensuring permanent access to important external links.
- **De-risks the Moonshot:** It forces us to solve the core technical challenges of external data extraction and ingestion in a controlled, user-triggered environment.
- **Enriches RAG Immediately:** The knowledge base becomes more valuable with every import, making the existing RAG features more powerful long before the fully proactive Oracle is built.

## 5. Success Criteria
- [ ] Within 30 days, a user can post `/import [URL]` in a chat, and the system successfully archives the content.
- [ ] After a successful import, a user can ask a question related to the imported content, and the RAG system provides a relevant answer from the archived text.
- [ ] The import process is robust enough to handle at least 80% of common news articles and blog posts.

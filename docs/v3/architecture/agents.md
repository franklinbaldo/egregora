# Agents

Egregora uses **LLM Agents** to perform complex semantic tasks.

## Writer Agent
*   **Role:** Editor/Journalist.
*   **Input:** Conversation Window (XML).
*   **Output:** Markdown Post.
*   **Tools:** RAG (Search past posts).

## Enricher Agent
*   **Role:** Librarian/Researcher.
*   **Input:** Raw `Entry` (with media/links).
*   **Output:** `Enrichment` Document (Description, Tags, Slug).

## Banner Agent
*   **Role:** Illustrator.
*   **Input:** Post Title/Summary.
*   **Output:** Image (Banner).

# RFC: The Egregora Atlas
**Status:** Moonshot Proposal
**Date:** 2024-07-25
**Disruption Level:** Total Paradigm Shift

## 1. The Vision
Imagine opening your Egregora site and not seeing a list of posts. Instead, you see a dynamic, explorable 2D map of your group's collective mind.

- **Concepts as Continents:** Major recurring themes (e.g., "Project Phoenix," "Q3 Marketing Strategy," "Team Offsite") are landmasses.
- **Conversations as Rivers:** The flow of discussion on a topic is a river carving its way through a continent.
- **Decisions as Cities:** Key decisions, action items, or commitments are fortified cities on the map, easily identifiable.
- **People as Trade Routes:** Lines connect concepts and decisions based on who participated, showing the flow of influence and expertise.

The user can zoom, pan, and click on any element. Clicking a "City" shows the exact message where a decision was made. Clicking a "River" replays the conversation. This transforms the output from a static, passive archive into a dynamic, engaging tool for understanding.

## 2. The Broken Assumption
This proposal challenges the most fundamental assumption of Egregora: **that the output must be a linear, chronological blog.**

> "We currently assume that the best way to represent knowledge is a series of documents sorted by date. This forces users to find information by remembering *when* something was said, not *what* it connects to. This prevents us from revealing the true, networked structure of our group's knowledge."

## 3. The Mechanics (High Level)
*   **Input:** We already have the core inputs: chat logs, entities, and document summaries. We may need to add a "connection strength" signal between concepts.
*   **Processing:**
    1.  **Graph Generation:** Instead of writing Markdown files, the primary output of the Writer Agent becomes a graph structure (e.g., JSON Graph Format). Nodes are concepts, people, and decisions. Edges are the relationships between them.
    2.  **Layout Engine:** A force-directed graph layout algorithm (like D3.js) runs to position the nodes in a visually intuitive way, forming the "continents" and "cities."
    3.  **Vectorial Mapping:** The RAG vector embeddings are used to determine the proximity of concepts on the map. Similar ideas cluster together naturally.
*   **Output:** The primary output is a single HTML page with an embedded, interactive map visualization, replacing the MkDocs site. The raw data (Markdown, conversation snippets) is still available when a user clicks on a node.

## 4. The Value Proposition
This is a 10x transformation.
- **From Reading to Exploring:** It changes the user's cognitive mode from passive reading to active exploration and discovery.
- **Intuitive Navigation:** It allows users to discover information based on context and relationships, not just search queries or dates.
- **Reveals Hidden Structures:** It makes the invisible power structures, decision-making patterns, and core ideas of the group visible at a glance. It answers "What's *really* going on in this team?"

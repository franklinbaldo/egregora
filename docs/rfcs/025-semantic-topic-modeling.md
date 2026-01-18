# RFC: Semantic Topic Modeling
**Status:** Quick Win Proposal
**Date:** 2026-01-20
**Disruption Level:** Moderate

## 1. The Vision
Before we can build a 3D world (The Atlas), we must first prove we can automatically organize chaos into structure. This RFC proposes adding a **Semantic Topic Modeling** step to the pipeline. This step will analyze the vector embeddings of all generated posts, automatically cluster them into "Topics," and assign human-readable labels to those clusters using an LLM.

The result is a new way to browse the site: a "Topics" page that groups content by *meaning*, not just by manual tags or date. It's the 2D blueprint for the future 3D world.

## 2. The Broken Assumption
This proposal challenges the assumption that **organization requires manual effort (tagging).**

> "We currently rely on manual tags or broad categories. This proposal asserts that the AI can self-organize the content based on its actual semantic substance, revealing the *true* structure of the conversation, not just the intended one."

## 3. The Mechanics (Implementation)
*   **Input:** Existing embeddings in `LanceDB`.
*   **Pipeline Step:** Create a new `TopicModelingStep`.
*   **Algorithm:**
    1.  Fetch embeddings from `LanceDB`.
    2.  Use `scikit-learn` (already a dependency) to perform clustering (e.g., K-Means or DBSCAN) on the vectors.
    3.  For each cluster, sample the central documents and prompt an LLM (via `pydantic-ai`) to generate a concise title and description for the topic.
*   **Output:** A `topics.json` artifact mapping `topic_id` -> `[post_ids]`.
*   **Visualization:** A simple static page in the MkDocs site that lists these dynamic topics and their associated posts, or perhaps a simple 2D scatter plot using a lightweight JS library.

## 4. The Value Proposition
This is an immediate, high-value feature that improves content discovery with zero manual effort from users. It validates the core technology stack (Embeddings + Clustering + LLM Labeling) required for the Moonshot "Atlas" vision, de-risking the larger project while delivering a "smart categorization" feature today. It answers the question: "What do we actually talk about?" with data, not guesses.

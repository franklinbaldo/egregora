# RFC: Related Concepts API
**Status:** Actionable Proposal
**Date:** 2024-07-26
**Disruption Level:** Low - Fast Path

## 1. The Vision
This RFC proposes creating a simple, machine-readable endpoint that exposes the core of Egregora's "memory." This API will take a concept (a text query) and return a structured list of the most relevant posts from the knowledge base. This is the first, crucial step toward the **Egregora Oracle** moonshot, providing the foundational mechanism for the Oracle to retrieve context.

Simultaneously, it delivers immediate user value by dramatically improving the "Related Posts" feature on the existing static site, making it dynamic and more accurate.

## 2. The Broken Assumption
This breaks the assumption that the RAG vector index is a private, internal detail of the `write` pipeline. Instead, it treats the knowledge base as a first-class product artifact, meant to be queried and exposed.

## 3. The First Implementation Path (≤30 days)
1.  **Create a New CLI Command:** Add `egregora query-index` to the CLI.
2.  **Input:** The command will accept a string query: `egregora query-index "Project Phoenix cost overruns"`.
3.  **Logic:**
    - Load the existing LanceDB index.
    - Convert the input query into an embedding using the same model as the indexer.
    - Perform a vector similarity search against the index and retrieve the top 5-10 document IDs (post slugs).
4.  **Output:** The command will print a JSON object to stdout containing a list of results, each with the document ID and a relevance score.
5.  **Integration with Site Generation:**
    - During the `write` process, after the index is built, iterate through every generated post.
    - For each post, run its title and summary through the `query-index` logic to find its most related peers.
    - Write this mapping to a single `related.json` file in the site's root directory.
    - Modify the blog post template to fetch and display related posts from this JSON file using client-side JavaScript, replacing the current, less accurate method.

## 4. The Value Proposition
- **De-risks the Oracle:** This proves the core technical capability (querying the knowledge base) is viable without the complexity of building a real-time chatbot.
- **Immediate User Benefit:** Delivers a significantly better "Related Posts" experience, increasing engagement and knowledge discovery on the existing site.
- **Foundation for the Future:** This API is the first brick in the road to the Oracle. Every future interactive feature will be built on top of this foundation.

## 5. Success Criteria
- A new `related.json` file is generated alongside the static site.
- The "Related Posts" section on each blog page is powered by this new data and shows more relevant links than the previous implementation.
- The implementation adds no more than 10% to the total site generation time.

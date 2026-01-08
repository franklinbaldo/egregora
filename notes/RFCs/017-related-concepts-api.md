# RFC: The "Related Concepts" API
**Status:** Actionable Proposal
**Date:** 2024-07-26
**Disruption Level:** Low - Fast Path

## 1. The Vision
This RFC proposes a small, surgical addition to the existing Pure pipeline. During the build process, we will generate a `_concepts.json` file. This file will contain a simple key-value map of the most important concepts, entities, and decisions discussed, with links to the posts where they are mentioned. We will then ship a tiny, local-only FastAPI or Flask server that serves this JSON file. This provides immediate value by allowing developers and power-users to programmatically query the knowledge base, serving as a powerful validation of the "Collective Memory" vision.

## 2. The Broken Assumption
We assume that the only useful output of the pipeline is human-readable documents (the blog). This RFC challenges that by proposing that a machine-readable summary of the knowledge is an equally valuable, and perhaps more powerful, artifact.

## 3. The First Implementation Path (≤30 days)
- **Step 1 (Taxonomy Extraction):** Modify the existing Taxonomy Agent. After it generates tags for a post, have it also extract key entities (people, projects, technologies) and decisions made.
- **Step 2 (JSON Generation):** Add a new step to the `PipelineRunner` that aggregates these extracted concepts from all posts into a single `_concepts.json` file and saves it to the site output directory.
- **Step 3 (Local API):** Create a new, simple `egregora serve` command (using Typer) that launches a `uvicorn` server to serve the contents of the `_concepts.json` file at a local port (e.g., `http://localhost:8001/api/concepts`).
- **Step 4 (Documentation):** Add a section to the README explaining how to use this experimental API.

## 4. The Value Proposition
This is the fastest possible way to de-risk the "Collective Memory" moonshot. It proves we can extract a queryable knowledge model from the conversations and demonstrates the value of having an API, however simple. It unlocks immediate use cases like building custom dashboards or integrating with tools like Raycast or Alfred, all without breaking the existing static-site generation flow.

## 5. Success Criteria
- A `_concepts.json` file is generated with every `egregora write` run.
- The `egregora serve` command successfully serves the JSON content.
- At least one internal script or tool is built that consumes this new API.

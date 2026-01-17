# RFC: Portable Knowledge Artifacts
**Status:** Actionable Proposal
**Date:** 2026-01-17
**Disruption Level:** Low - Immediate Utility

## 1. The Vision
This proposal defines a standardized, versioned serialization format for Egregora's extracted knowledge: the **Portable Knowledge Artifact (PKA)**. A PKA is a zipped archive containing structured data (`decisions.json`, `entities.json`), metadata (`manifest.toml`), and human-readable summaries (`summary.md`). It is the atomic unit of knowledge exchange.

## 2. The Broken Assumption
This proposal breaks the assumption that **Egregora's internal state is only relevant to itself.**

> "We currently assume that the extracted knowledge lives only in the local DuckDB/LanceDB for the purpose of generating a site. This proposal asserts that the extracted knowledge is a valuable asset in its own right that should be portable, shareable, and ingestible."

## 3. The First Implementation Path (≤30 days)
-   **Define the Schema**: Create a Pydantic model `KnowledgeArtifact` that defines the structure of the export (Manifest + Data Layers).
-   **Implement `ExportAdapter`**: A new output adapter that serializes the current window's knowledge into a PKA `.zip` file.
-   **Implement `ImportAdapter`**: A new input adapter that can read a PKA file as a source, effectively allowing one Egregora to "read" another's output.
-   **CLI Command**: `egregora export --format pka --output knowledge.zip`

## 4. The Value Proposition
1.  **Backup & Restore**: A clean way to backup the *intelligence* without backing up the massive raw logs.
2.  **Manual Federation**: The "Sneakernet Mesh". I can email you my team's "Decisions of 2025" package, and you can ingest it into your Egregora to query it.
3.  **Migration**: Moving from local to cloud (or API) becomes trivial.
4.  **Prerequisite**: This is the mandatory data packet format for the "Egregora Mesh" moonshot.

## 5. Success Criteria
-   `src/egregora/schemas/artifact.py` defines the PKA structure.
-   `egregora export` command produces a valid zip.
-   `egregora build --adapter pka --input knowledge.zip` successfully generates a site from the artifact.

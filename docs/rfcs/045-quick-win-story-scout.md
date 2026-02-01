# RFC 045: Story Scout (Arc Detection CLI)

- **Author**: Visionary Persona
- **Date**: 2026-02-02
- **Status**: Proposed
- **Type**: Quick Win 🐇
- **Ladder**: Steps toward [RFC 044 (Director)](./044-moonshot-egregora-director.md)

## 1. Problem Statement

Egregora currently uses **rigid time-based windowing** (e.g., "7 days per post").
This is blind to the actual content.
-   A 3-day vacation gets chopped if it crosses a window boundary.
-   A month of silence generates empty/boring posts.
-   Users have no way to "see" what the system will write about without running the full expensive generation.

## 2. Proposed Solution: Story Scout

We propose a new CLI command: `egregora scout <input_file>`.

This tool will:
1.  **Ingest** the chat export (fast parse).
2.  **Embed** the messages (using `lancedb` + `sentence-transformers` locally or API).
3.  **Cluster** the messages using `scikit-learn` (K-Means or DBSCAN) to find semantic densities.
4.  **Report** a "Table of Contents" of detected arcs.

**Example Output:**
```text
$ egregora scout chat.zip

found 12 potential story arcs:

| ID | Date Range | Msg Count | Key Terms          | Confidence |
|----|------------|-----------|--------------------|------------|
| 01 | 2024-01-05 | 45        | pizza, mario, yum  | High       |
| 02 | 2024-02-12 | 120       | road, trip, vegas  | High       |
| 03 | 2024-03-01 | 5         | (sparse chatter)   | Low        |
...
```

## 3. Value Proposition

*   **Visibility**: Users can see the "shape" of their chat history instantly.
*   **Validation**: Proves we can detect "Arcs" (essential for RFC 044).
*   **Optimization**: Users can tweak the `window_size` config based on the Scout's report *before* running the full write.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Story Scout CLI

  As a user preparing to generate a blog
  I want to scan my chat history for story arcs
  So that I can understand the content distribution without waiting for full generation

  Scenario: Basic Scan
    Given a chat export with a distinct "Birthday Party" event
    When I run `egregora scout chat.zip`
    Then the output should list a cluster corresponding to the "Birthday Party" dates
    And the cluster summary should include keywords like "birthday", "cake", "party"

  Scenario: JSON Output
    Given I run `egregora scout chat.zip --json`
    Then the output should be valid JSON
    And the JSON should contain a list of "arcs" with "start_date", "end_date", and "message_count"

  Scenario: Empty/Noise Filtering
    Given a chat log with scattered "ok", "lol" messages
    When I run the scout
    Then it should mark low-density periods as "Low Confidence" or exclude them
```

## 5. Implementation Plan (Total: 5 Days)

*   **Day 1: Ingestion & Embedding**
    *   Reuse `src/egregora/input_adapters` to read the zip.
    *   Reuse `src/egregora/rag/embeddings.py` to generate vectors.

*   **Day 2: Clustering Logic**
    *   Implement `sklearn.cluster.KMeans` or `DBSCAN` on the vectors.
    *   Tune hyperparameters (epsilon, min_samples) for "chat density".

*   **Day 3: Keyword Extraction**
    *   Use TF-IDF on the clusters to find representative "Key Terms".

*   **Day 4: CLI Interface**
    *   Add `scout` command to `main.py`.
    *   Format output with `rich.table`.

*   **Day 5: Testing**
    *   Unit tests for the clustering function.
    *   Snapshot tests for the CLI output.

## 6. Success Metrics

*   **Speed**: Scan 1 year of chat in < 30 seconds (using local embeddings).
*   **Accuracy**: "Key Terms" should look meaningful to the user (not stop words like "the", "and").

# RFC 037: Egregora Echo (CLI Chat Command)

- **Author**: Visionary Persona
- **Date**: 2026-02-02
- **Status**: Proposed
- **Type**: Quick Win 🐇
- **Ladder**: Steps toward [RFC 036 (Nexus)](./036-moonshot-egregora-nexus.md)

## 1. Problem Statement

The "Contextual Memory" (RAG) feature in Egregora is currently only used during the batch generation of blog posts. If a user wants to query their memory ad-hoc (e.g., "What was the name of that restaurant?"), they have no easy way to do so without triggering a full site build or inspecting the database manually.

## 2. Proposed Solution: Egregora Echo

We propose adding a simple CLI command: `egregora ask`.

This command will:
1.  Load the existing LanceDB vector store.
2.  Take a natural language query from the user.
3.  Retrieve relevant chunks using the `EmbeddingRouter`.
4.  (Optional) Pass the chunks to the LLM to synthesize an answer.

This validates the core retrieval logic required for the Moonshot (Nexus) but delivers immediate value in the terminal.

## 3. Value Proposition

*   **Immediate Access**: "Google your past" from the command line.
*   **Debugging**: Allows developers to verify RAG quality easily ("Why did the bot think X?").
*   **Zero-Config**: Uses the existing `.egregora/` state from the `write` command.

## 4. BDD Acceptance Criteria

```gherkin
Feature: CLI Chat Command (Echo)

  As a user who has generated an Egregora site
  I want to ask questions about my chat history in the terminal
  So that I can recall information without regenerating the site

  Scenario: Direct Question Answering
    Given a valid Egregora site with a populated RAG index
    When I run `egregora ask "Where did we go for dinner?"`
    Then the system should retrieve relevant memory chunks
    And the output should contain the synthesized answer "You went to Mario's Pizza."
    And the output should cite the source date (e.g., "Found in: 2023-05-12")

  Scenario: No Index Found
    Given a fresh Egregora site with no RAG index
    When I run `egregora ask "Hello"`
    Then the system should exit with a helpful error
    And the error should suggest running `egregora write` first

  Scenario: Debug Mode
    Given I run `egregora ask "query" --debug`
    When the answer is generated
    Then the output should show the raw retrieved chunks and their similarity scores
```

## 5. Implementation Plan (Total: 3 Days)

*   **Day 1: Command Structure**
    *   Add `ask` command to `src/egregora/cli/main.py`.
    *   Load `EgregoraConfig` and verify RAG availability.

*   **Day 2: Retrieval Logic**
    *   Reuse `EmbeddingRouter` from `src/egregora/rag/embedding_router.py`.
    *   Implement a simple `answer_question` function using the configured LLM.

*   **Day 3: Polish & Output**
    *   Format output with `rich` (highlighting quotes, dates).
    *   Add error handling for missing API keys or indices.

## 6. Success Metrics

*   **Latency**: Query to Answer < 5 seconds.
*   **Utility**: Can successfully answer "What is X?" questions from test datasets.

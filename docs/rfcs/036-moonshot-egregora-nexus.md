# RFC 036: Egregora Nexus (The MCP Interface)

- **Author**: Visionary Persona
- **Date**: 2026-02-02
- **Status**: Proposed
- **Type**: Moonshot 🔭

## 1. Problem Statement

Egregora effectively transforms chat logs into a static archive (MkDocs site). However, this archive is **passive** and **siloed**.

- **Passive**: To access memories, the user must stop what they are doing, navigate to a website, and search.
- **Siloed**: The rich semantic data (vector embeddings, entities, summaries) is locked within Egregora's internal DuckDB/LanceDB files, inaccessible to the user's other tools (IDEs, writing assistants, AI agents).

We are building a "Digital Soul" that is trapped in a glass box.

## 2. Proposed Solution: Egregora Nexus

We propose transforming Egregora into a **Model Context Protocol (MCP) Server**.

[MCP](https://modelcontextprotocol.io/) is an open standard that enables AI assistants (like Claude Desktop, Cursor, etc.) to connect to external data sources. By implementing an MCP server, Egregora becomes a "memory provider" for the entire AI ecosystem.

### Key Components

1.  **Nexus Server**: A lightweight FastMCP server (using `mcp` library) that runs alongside the static site or as a background daemon.
2.  **Resources**: Expose raw chat logs and generated blog posts as MCP Resources (`egregora://posts/{slug}`).
3.  **Tools**: Expose retrieval tools (`search_memories`, `get_profile`) to the connecting client.
4.  **Prompts**: Expose standard prompts (`summarize_relationship`) that leverage the local data.

## 3. Value Proposition

*   **Universal Access**: Users can ask "What did I discuss with X?" directly inside their IDE or writing tool.
*   **Contextual AI**: An AI coding assistant could know the *history* of a project from chat logs, not just the code files.
*   **Future-Proofing**: Adopting a standard protocol (MCP) prevents vendor lock-in and ensures Egregora works with future AI clients.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Egregora MCP Server

  As a user with an MCP-compliant AI client (e.g., Claude Desktop)
  I want to connect to my Egregora instance
  So that my AI assistant has access to my personal memories

  Scenario: Discovering Memory Resources
    Given the Egregora Nexus server is running
    When the MCP client requests a list of resources
    Then the server should return a list of generated blog posts
    And the resources should include metadata (title, date, author)

  Scenario: Semantic Search via Tool Use
    Given I am chatting with an AI assistant connected to Nexus
    When I ask "What did I say about 'Project Titan' last year?"
    Then the assistant should call the `search_memories` tool
    And the tool should query the LanceDB vector store
    And the assistant should receive relevant chat snippets as context

  Scenario: Profile Retrieval
    Given the Egregora Nexus server is running
    When the assistant calls `get_profile` with argument "Alice"
    Then the server should return the generated bio and traits for "Alice"
    And the response should include the generated avatar path
```

## 5. Implementation Hints

1.  **Dependency**: Add `mcp` to `pyproject.toml`.
2.  **Entry Point**: Create `src/egregora/nexus/server.py`.
3.  **Integration**: Use `FastMCP` to wrap the existing `egregora.rag` and `egregora.database` modules.
4.  **Lifecycle**: Add `egregora serve` command to the CLI to start the MCP server.

## 6. Risks

*   **Security**: Exposing personal data via a local server port requires strict access control (though MCP over Stdio mitigates this for local use).
*   **Performance**: Loading the RAG models (LanceDB) might be heavy for a background process. We need lazy loading.
*   **Dependency Bloat**: Adding server capabilities might complicate the "simple static site generator" positioning. (Mitigation: Make it an optional extra).

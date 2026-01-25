# 🔭 RFC 026: The Universal Context Layer

**Feature**: Universal Context Layer
**Authors**: @visionary
**Status**: Proposed
**Created**: 2026-01-22
**Moonshot**: Yes

---

## 1. Problem Statement

Egregora is currently a "destination". To access the collective intelligence of the team, a user must:
1. Stop their current work (context switch).
2. Run a CLI command (high friction).
3. Wait for generation.
4. Navigate to a static HTML site.
5. Search for information.

This friction means Egregora is only used for "deep research" or "post-mortem" analysis, not for daily decision-making. The "Collective Brain" is disconnected from the "Working Hands" (IDE, Git, Jira).

## 2. Proposed Solution

We propose transforming Egregora from a **Site Generator** into a **Context Platform**.

The **Universal Context Layer** is a standardized API and plugin architecture that allows Egregora to inject historical context directly into external tools.

**Key Components:**
1. **Context Server**: A lightweight, always-on (or on-demand) server that exposes RAG and Knowledge Graph capabilities via an API (MCP - Model Context Protocol, or standard REST/gRPC).
2. **Context Adapters**: Plugins for VS Code, JetBrains, GitHub Actions, and Slack that query the Context Server.
3. **Context Resolution**: The ability to resolve a "Cursor Position" (File: `src/main.py`, Line: 42, Git SHA: `abc1234`) into a set of relevant historical discussions.

## 3. Value Proposition

- **Zero-Friction Access**: Developers get answers without leaving their IDE.
- **Proactive Intelligence**: Egregora warns you *before* you make a mistake ("Last time we touched this file, it caused incident #123").
- **Ubiquitous Memory**: The "Team Brain" is present in every tool, ensuring consistency.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Universal Context Layer
  As a developer
  I want to access team knowledge directly in my workflow
  So that I don't have to context-switch to find answers

Scenario: IDE Context Look-up
  Given I am editing "src/egregora/orchestration/runner.py" in VS Code
  And the Universal Context Layer is active
  When I ask "Why is the window size 100?"
  Then the system returns a summary of the chat discussion from "2024-12-15" where this decision was made
  And provides a link to the original conversation

Scenario: PR Review Context Injection
  Given I open a Pull Request modifying "src/egregora/agents/writer.py"
  When the Context Bot runs
  Then it posts a comment summarizing past changes to this file
  And flags that "Writer Agent stability" has been a recurring topic in the last 3 sprints

Scenario: Error Boundary Context
  Given I encounter a "PromptTooLargeError" in the CLI
  When the error is displayed
  Then the CLI automatically queries the Context Layer
  And displays "This error was last seen 2 days ago by @sapper. Fix: Increase window split threshold."
```

## 5. Implementation Hints

- **Model Context Protocol (MCP)**: Adopt Anthropic's open standard for connecting LLMs to context. This makes us compatible with Claude Desktop and other tools out of the box.
- **Server Mode**: Extend `egregora` CLI with a `serve-context` command.
- **LSP-like Architecture**: Structure the Context Server similar to a Language Server Protocol (LSP) server, but for "Organizational Knowledge" instead of "Syntax".

## 6. Risks

- **Privacy/Security**: Exposing internal chat logs via an API increases the attack surface. Authentication must be robust.
- **Latency**: RAG lookups must be sub-second to feel "native" in an IDE.
- **Noise**: Proactive context can become "Clippy" if not tuned for high relevance.

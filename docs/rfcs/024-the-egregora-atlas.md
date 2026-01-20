# 024 - The Egregora Atlas

**Status:** PROPOSED
**Type:** MOONSHOT 🔭
**Driver:** Visionary

## Problem Statement
We currently assume that a group's history is best represented as a **chronological log** (a blog). However, human thought is **associative**, not linear. A blog format buries the evolution of ideas under the weight of time. To find how a specific concept (e.g., "AI Safety") developed, a user must manually search and piece together disparate posts, often missing the subtle connections and branching discussions that actually formed the group's consensus.

## Proposed Solution
**The Egregora Atlas** transforms the output from a flat website into a **spatial knowledge graph**.

The Atlas is an interactive, 2D/3D visualization where:
- **Nodes** are blog posts, key decisions, or distinct concepts.
- **Edges** represent semantic similarity (derived from LanceDB embeddings) or explicit references.
- **Clusters** reveal the major "epochs" or "themes" of the group's thinking.

Users can "fly" through the history of the group, seeing how a small spark of an idea in 2023 exploded into a major project in 2024. The AI acts as a "Cartographer," labeling these clusters and generating "Guided Tours" through the graph (e.g., "The History of Our Architecture").

## Value Proposition
- **From Archives to Assets**: Turns a passive archive into an active tool for onboarding and synthesis.
- **Discovery**: Users find connections they didn't know existed.
- **Context**: New members can visualize the "shape" of the group's wisdom in seconds.
- **Differentiation**: Moves Egregora from "Just another blog generator" to "The Operating System for Group Intelligence."

## BDD Acceptance Criteria

```gherkin
Feature: The Atlas Interface
  As a curious reader
  I want to explore the group's history spatially
  So that I can understand the evolution of ideas beyond simple chronology

  Scenario: Visualizing the Knowledge Graph
    Given the blog has 50+ posts with vector embeddings
    And I navigate to the "/atlas" page
    When the visualization loads
    Then I see a graph where nodes represent posts
    And nodes with high semantic similarity are visually clustered together
    And the clusters are automatically labeled with their dominant theme (e.g., "Optimization", "Team Culture")

  Scenario: Traversing Connections
    Given I am viewing the node for "Post A"
    When I click on a connected node "Post B"
    Then the view focuses on "Post B"
    And the sidebar displays the AI-generated explanation of why A and B are connected (e.g., "Both discuss recursive logic")

  Scenario: Guided Tours
    Given I am new to the group
    When I select the "Architecture Evolution" tour
    Then the interface automatically flies me through the relevant nodes in chronological order
    And an overlay provides a narrative summary of the progression
```

## Implementation Hints
- **Frontend**: Use libraries like `d3.js`, `cytoscape.js`, or `three.js` (via `react-force-graph`) to render the graph.
- **Data**: Expose the LanceDB embeddings and metadata as a JSON artifact during the build process.
- **AI**: Use the `WriterAgent` to generate labels for clusters and descriptions for edges ("Why are these related?").
- **Integration**: Embed the visualization as a special page in the MkDocs site, potentially overriding the default theme.

## Risks
- **Complexity**: Graph visualizations can easily become "hairballs" (unreadable messes). Good UX/UI design is critical.
- **Performance**: Large graphs can lag in the browser. We may need to limit nodes or use WebGL.
- **Meaning**: Embeddings are mathematical; they don't always map to human intuition. The connections might seem random without good AI explanation.

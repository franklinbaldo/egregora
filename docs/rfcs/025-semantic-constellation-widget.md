# 025 - Semantic Constellation Widget

**Status:** PROPOSED
**Type:** QUICK WIN ⚡
**Driver:** Visionary
**Relation to Moonshot:** This is the foundational data layer and "mini-atlas" for the full [Egregora Atlas](./024-the-egregora-atlas.md).

## Problem Statement
When a user finishes reading a blog post, the only options are "Previous" or "Next" (chronological). This forces a linear reading path, even if the most relevant related content happened 6 months ago. Users miss valuable context because they can't see the semantic threads connecting disparate posts.

## Proposed Solution
Add a **"Semantic Constellation"** widget to the footer of every blog post.

This widget will:
1.  Query LanceDB for the 3-5 most semantically similar posts.
2.  Use the `WriterAgent` to generate a one-sentence "bridge" explaining the connection (e.g., "Also discusses the trade-off between speed and safety").
3.  Render this as a visually distinct section (e.g., a card grid or mini-list) at the bottom of the post.

This proves we can use RAG for *navigation*, not just *generation*, and creates the "edges" for the future Atlas.

## Value Proposition
- **Increased Engagement**: Users read more posts because the recommendations are actually relevant.
- **Better Context**: Explicitly stating *why* posts are related helps users build a mental model of the domain.
- **Proof of Capability**: De-risks the "Atlas" by validating that our embeddings produce meaningful clusters.

## BDD Acceptance Criteria

```gherkin
Feature: Semantic Constellation Widget
  As a reader
  I want to see semantically related posts with context
  So that I can follow a thread of thought across time

  Scenario: Displaying the widget
    Given I am reading a generated blog post
    When I scroll to the bottom of the content
    Then I see a "Related Constellations" section
    And it contains 3 to 5 links to other posts
    And the links are NOT just the chronological previous/next posts

  Scenario: Contextual Explanations
    Given the widget is displayed
    When I look at a recommended link
    Then I see a short AI-generated sentence explaining why it is related
    And the explanation is specific to the content (e.g., not just "Related post")
```

## Implementation Plan (30 Days)

- [ ] **Week 1: Data Pipeline (Days 1-5)**
    - Modify the `WriterAgent` pipeline to query LanceDB for neighbors *after* a post is generated (or during a post-processing pass).
    - Create a new `RelationSchema` to store `(source_slug, target_slug, reason)`.

- [ ] **Week 2: AI Logic (Days 6-10)**
    - Create a prompt for the `WriterAgent` (or a lightweight `LibrarianAgent`) to take two summaries and generate a "bridge sentence".
    - Implement the logic to generate these bridges for all existing posts.

- [ ] **Week 3: Frontend Integration (Days 11-15)**
    - Modify the MkDocs template (using `mkdocs-material` overrides) to inject this data into the post footer.
    - Ensure it looks good on mobile.

- [ ] **Week 4: Testing & Polish (Days 16-20)**
    - Verify that recommendations aren't hallucinations.
    - Tune the similarity threshold in LanceDB.
    - Ship it.

## Success Metrics
- **Click-through rate (CTR)** on the widget links (if analytics are enabled).
- **Time on site** (qualitative or simulated).
- **Subjective Quality**: Do the "bridge sentences" make sense to a human reader?

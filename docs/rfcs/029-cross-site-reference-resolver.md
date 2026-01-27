# RFC 029: Cross-Site Reference Resolver

**Title:** Cross-Site Reference Resolver
**Status:** Draft
**Type:** Quick Win ⚡
**Relation to Moonshot:** The first "synapse" of the **Egregora Mesh** (RFC 028).
**Created:** 2026-01-26

## Problem Statement

**The Pain:** Broken context across boundaries.
If I am writing a blog post in my "Personal" Egregora site and I want to reference a discussion from my "Work" Egregora site, I can only paste a dumb URL. The reader has to click, leave the context, authenticate (maybe), and read the other page. There is no preview, no summary, and no semantic connection. The web is full of dead links and friction.

## Proposed Solution

**The Fix:** A "Smart Embed" system for Egregora URLs.

We will implement a `ReferenceResolver` component that:
1.  Detects links to other Egregora sites (identified by `generator="Egregora"` meta tags or Atom feeds).
2.  Fetches the target Atom Entry (XML).
3.  Generates a "Reference Card" (embedded HTML/Markdown) containing:
    *   Title
    *   Summary/Excerpt
    *   Author (Name/Avatar)
    *   Date
    *   Source Site Name

This uses public (or accessible) Atom feeds, requiring no complex authentication for the MVP. It proves we can treat external Egregora instances as structured data sources.

## Value Proposition

*   **Immediate Utility:** Makes cross-linking between personal and team blogs beautiful and useful.
*   **Proof of Concept:** Validates the "Atom as Protocol" approach for the Mesh.
*   **Engagement:** Readers are more likely to explore related context if it's previewed inline.

## BDD Acceptance Criteria

```gherkin
Feature: Smart Reference Embedding
  As a Reader of an Egregora blog
  I want links to other Egregora posts to appear as rich summary cards
  So that I can understand the referenced context without leaving the page

  Scenario: Resolving a valid Egregora Link
    Given a blog post contains the URL "https://other-egregora.site/posts/2025-01-01-entry.html"
    And "https://other-egregora.site/feed.xml" is a valid Egregora Atom feed
    When the site is generated
    Then the URL should be replaced by a `<div class="reference-card">`
    And the card should display the title "Entry Title" from the remote feed
    And the card should display the source "other-egregora.site"

  Scenario: Handling Non-Egregora Links
    Given a blog post contains the URL "https://google.com"
    When the site is generated
    Then the URL should remain a standard HTML link
    And no reference card should be generated

  Scenario: Graceful Failure (404/Offline)
    Given a blog post contains a link to a dead Egregora site
    When the resolver attempts to fetch the feed
    Then it should fail gracefully (timeout/404)
    And the link should revert to a standard text link (no broken UI)
```

## Implementation Plan

- [ ] **Day 1-2:** Create `ReferenceResolver` class in `src/egregora/rendering/`.
- [ ] **Day 3-4:** Implement HTTP fetcher with caching (don't ddos sites during build).
- [ ] **Day 5-6:** Implement Atom XML parser (using `feedparser` or `lxml`) to extract metadata.
- [ ] **Day 7-8:** Create Jinja2 template for `reference_card.html`.
- [ ] **Day 9-10:** Integrate into `WriterAgent` or `Materializer` as a post-processing step.
- [ ] **Total:** ~10 days.

## Success Metrics

*   **Resolver Success Rate:** % of Egregora links successfully expanded.
*   **Build Time Impact:** < 10% increase in build time (due to HTTP fetches).

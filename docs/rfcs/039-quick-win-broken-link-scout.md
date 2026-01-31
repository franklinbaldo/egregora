# RFC 039: Broken Link Scout (Gardening Quick Win)

**Status:** Draft
**Type:** Quick Win ⚡
**Author:** Visionary (Jules)
**Date:** 2026-01-29
**Relation:** Step 1 of [RFC 038: Egregora Gardener](038-moonshot-egregora-gardener.md)

---

## 1. Problem Statement

A key part of the "Egregora Gardener" vision is keeping the archive alive. The most immediate symptom of "Archive Rot" is broken external links (404s). Currently, users have no way to know which links in their generated blog are broken without clicking them one by one.

## 2. Proposed Solution

Implement a **Broken Link Scout** as a CLI command (`egregora garden scan`).
This tool will:
1.  Parse the generated site (or source database).
2.  Extract all external URLs.
3.  Check their HTTP status (HEAD request).
4.  Report broken links (404, 500, DNS failure) in a neat table.

This is the foundational "Sense" capability for the future "Act" capability (Auto-repair) of the Gardener.

## 3. Value Proposition

*   **Immediate Insight**: Users instantly see how much "rot" is in their archive.
*   **Trust**: Validates that the archive is healthy.
*   **Foundation**: Builds the code paths needed for the full Gardener (URL extraction, async checking).

## 4. BDD Acceptance Criteria

```gherkin
Feature: Broken Link Scout
  As a user maintaining a blog
  I want to scan for broken external links
  So that I can identify rot in my archive

  Scenario: Scanning a healthy archive
    Given a blog with 5 posts containing valid URLs (200 OK)
    When I run `egregora garden scan`
    Then the output should show "0 broken links found"
    And the exit code should be 0

  Scenario: Detecting broken links
    Given a blog post with a link to "http://example.com/dead-link-123"
    And "http://example.com/dead-link-123" returns 404
    When I run `egregora garden scan`
    Then the output should list "http://example.com/dead-link-123" as BROKEN (404)
    And the exit code should be 1 (or non-zero)

  Scenario: Handling timeouts
    Given a link to "http://timeout.com"
    And the server hangs
    When I run `egregora garden scan`
    Then the tool should timeout after 5 seconds (per link)
    And report the link as UNREACHABLE
```

## 5. Implementation Plan (30 Days)

*   **Week 1: Scaffolding & Extraction**
    *   Create `src/egregora/cli/garden.py`.
    *   Implement URL extraction from `messages` table (Ibis).
*   **Week 2: Async Checker**
    *   Implement `LinkChecker` class using `httpx` (async).
    *   Handle rate limits and timeouts.
*   **Week 3: Reporting & Polish**
    *   Use `rich` to print a beautiful table of results.
    *   Add `--output json` for machine readability.
*   **Week 4: Testing & Docs**
    *   Add unit tests with `respx` to mock 404s.
    *   Update documentation.

## 6. Success Metrics

*   **Performance**: Scan 1000 links in < 60 seconds.
*   **Accuracy**: < 1% false positives (e.g., handling anti-bot 403s correctly).
```

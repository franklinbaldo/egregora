# RFC 043: Smart Links (The Auto-Linker)

**Status:** Proposed
**Type:** Quick Win 🐇
**Author:** Visionary (Jules)
**Date:** 2026-02-02
**Ladders to:** [RFC 042: Egregora Codex](./042-moonshot-egregora-codex.md)

---

## 1. Problem Statement

**The Friction**: Navigation in Egregora is currently **manual**.
If a user reads a post where "Mom" is mentioned, they cannot click "Mom" to see her profile. They have to manually go to the "Authors" index and find her. The text is "dead"—it contains semantic references but no functional links.

## 2. Proposed Solution: Smart Links

We will implement an **Auto-Linker** pipeline step that runs after content generation but before site building.

The Auto-Linker will:
1.  **Load Entities**: Build a registry of known entities (Authors from `profiles/`, Tags from `tags.md`, and potentially generated Pages).
2.  **Scan & Link**: Scan the Markdown content of every post.
3.  **Replace**: Automatically replace occurrences of entity names with Markdown links.
    *   `"Mom said..."` -> `"[Mom](../profiles/mom.md) said..."`
    *   `"This is #classic..."` -> `"This is [#classic](../tags.md#classic)..."`

This acts as the primitive "nervous system" for the future Egregora Codex (RFC 042).

## 3. Value Proposition

*   **Instant Connectivity**: Users can "surf" their memories immediately.
*   **Low Cost**: No new AI models needed; just clever string manipulation and existing metadata.
*   **Foundation**: Establishes the technical pattern for the future "Wiki" structure.

## 4. BDD Acceptance Criteria

```gherkin
Feature: Smart Links (Auto-Linker)
  As a reader of the archive
  I want key terms to be clickable links
  So that I can easily jump to related content

  Scenario: Linking Author Names
    Given an author profile exists for "Captain Reynolds" with slug "captain-reynolds"
    And a post contains the text "Captain Reynolds suggested we fly."
    When the Auto-Linker processes the post
    Then the text should become "[Captain Reynolds](../profiles/captain-reynolds.md) suggested we fly."

  Scenario: Handling partial matches (Safety)
    Given an author profile exists for "Rob"
    And a post contains the text "The robot malfunctioned."
    When the Auto-Linker processes the post
    Then it should NOT link "rob" inside "robot" (Whole word matching only)
    And the text should remain "The robot malfunctioned."

  Scenario: Linking Tags
    Given a tag "#adventure" is used in the archive
    And a post contains the text "It was a true #adventure."
    When the Auto-Linker processes the post
    Then the text should become "It was a true [#adventure](../tags.md#adventure)."
```

## 5. Implementation Plan (≤30 Days)

- [ ] **Day 1-2**: Create `LinkerRegistry` class to hold known entities (Authors/Tags).
- [ ] **Day 3-5**: Implement `LinkerWorker` with regex-based replacement logic (ensure whole-word matching and ignore existing links).
- [ ] **Day 6-7**: Integrate `LinkerWorker` into the `orchestration` pipeline (post-write).
- [ ] **Day 8**: Add tests (unit tests for regex safety, integration tests for pipeline).
- [ ] **Day 9**: Documentation and Polish.

## 6. Success Metrics

*   **Link Density**: Average number of internal links per post (Target: >3).
*   **Navigation Depth**: Increase in average pages visited per session (if analytics existed).
*   **User Joy**: "I can finally click on names!"
```

# 🔭 RFC 027: The Tuning Fork

**Status:** Draft
**Created:** 2026-01-26
**Persona:** Visionary
**Type:** Quick Win
**Relation:** Precursor to [RFC 026: The Autonomous Director](./026-the-autonomous-director.md)

## Problem Statement
Users currently have no easy way to "fix" a bad post. If Egregora generates a boring summary of an exciting party, the user's only option is to manually edit the Markdown file or dive into the complex `writer.jinja` template to change global settings. There is no "Try Again" button with controls.

## Proposed Solution
**The Tuning Fork** is a CLI command (`egregora tune <post_id>`) that enables interactive, specific optimization.

1.  **Interactive CLI:** The user selects a post to tune.
2.  **Variation Strategy:** The user provides a high-level directive (e.g., "Make it funnier", "Focus on the drama", "Explain the technical details").
3.  **Generation:** The system generates 3 parallel versions of the post using the new directive as a temporary system instruction overlay.
4.  **Selection:** The user sees a side-by-side diff (or summary) and picks the winner.
5.  **Persistence:** The winner replaces the file, AND the directive is saved as a "Style Preference" that can be optionally applied globally.

## Value Proposition
- **Immediate Satisfaction:** Users can fix specific "dud" posts instantly.
- **Accessible Control:** Gives users editorial control without requiring code changes.
- **Data Collection:** Every "Choice" made by the user is a labeled data point for training the future Autonomous Director.

## BDD Acceptance Criteria

```gherkin
Feature: Interactive Post Tuning

  As a user acting as an editor
  I want to regenerate a specific post with new instructions
  So that I can improve the quality of key memories

  Scenario: Tuning a Post
    Given a generated post "post-123.md" exists
    When I run `egregora tune post-123 --instruction "Make it more sarcastic"`
    Then the system should generate 3 variations using the original chat logs
    And I should be presented with a selection menu

  Scenario: Saving the Winner
    Given I am viewing the 3 variations
    When I select Variation B
    Then "post-123.md" should be overwritten with Variation B's content
    And the choice should be logged to `.egregora/tuning_history.json`
```

## Implementation Plan (30 Days)

- [ ] **Day 1-7:** Design `TuningEngine` class that wraps `Writer` agent, allowing injection of temporary system prompt overrides.
- [ ] **Day 8-14:** Implement CLI UI using `rich` to display diffs/options side-by-side.
- [ ] **Day 15-21:** Implement the "Winner Selection" logic and file replacement.
- [ ] **Day 22-30:** Add `tuning_history.json` logging to capture the dataset.

## Success Metrics
- **Usage Rate:** % of users who use `tune` command at least once.
- **Retention:** % of "tuned" posts that are NOT subsequently manually edited by the user.

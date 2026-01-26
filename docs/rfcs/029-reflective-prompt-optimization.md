# RFC 029: Reflective Prompt Optimization

**Title**: Reflective Prompt Optimization (Automated Feedback Loop)
**Status**: Proposed
**Persona**: Visionary
**Created**: 2026-01-26

## Relation to Moonshot
This is the first practical step toward [RFC 028: Egregora Autopoiesis](028-egregora-autopoiesis.md). It implements the "Extraction" and "Mutation" phases of the loop for a single target: the `custom_instructions` field.

## Problem Statement
The `writer.jinja` prompt encourages the AI to leave "System Feedback / TODOs" in its journal. Currently, this feedback is dead data. No one reads it consistently, and certainly no one manually updates the `writer.jinja` file every time the AI has a minor realization. This wastes the AI's "metacognitive" effort.

## Proposed Solution
Create a CLI command `egregora optimize-prompts` that:
1.  Reads the latest `Continuity Journal` markdown file.
2.  Parses the "System Feedback / TODOs" section.
3.  Uses a "Prompt Engineer" agent (LLM) to translate this raw feedback into a concrete improvement for `custom_instructions`.
4.  Outputs the new instruction set or creates a local git branch with the change.

## Value Proposition
- **Immediate Utility:** Makes the existing "System Feedback" section actually useful.
- **Low Effort:** Users get a "better tuned" bot just by running one command.
- **De-risked Autopoiesis:** Proves the closed-loop concept without the complexity of full self-rewriting code.

## BDD Acceptance Criteria

```gherkin
Feature: Reflective Prompt Optimization
  As a developer
  I want to apply the AI's self-suggestions
  So that the prompt quality improves over time

  Scenario: Extracting feedback from journal
    Given a journal file exists with:
      """
      ## System Feedback / TODOs
      - The tone was too dry. We should be more conversational.
      """
    And the current configuration has `custom_instructions = "Be formal."`
    When I run `egregora optimize-prompts --source latest-journal.md`
    Then the command output proposes: `custom_instructions = "Be formal but conversational."`
    And asks for confirmation to apply

  Scenario: Empty feedback handling
    Given a journal file exists with no "System Feedback" section
    When I run `egregora optimize-prompts`
    Then the command exits gracefully with "No feedback found"

  Scenario: Conflict Resolution
    Given multiple journals have conflicting feedback
    When I run `egregora optimize-prompts --all`
    Then the tool summarizes the conflict and asks for human choice
```

## Implementation Plan
- [ ] **Day 1-5**: Design the `FeedbackParser` class to extract sections from Markdown journals.
- [ ] **Day 6-15**: Implement the `PromptOptimizer` agent (using PydanticAI) that takes (Current Prompt + Feedback) -> New Prompt.
- [ ] **Day 16-25**: Build the CLI integration `egregora optimize-prompts`.
- [ ] **Day 26-30**: Add integration tests and documentation.

## Success Metrics
- **Usage:** % of users who run `optimize-prompts` after a batch generation.
- **Retention:** % of suggested changes that are kept (not reverted) by the user.

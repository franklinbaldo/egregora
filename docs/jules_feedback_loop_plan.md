# Plan: Implement Jules Feedback Loop

This plan outlines the implementation of a feedback loop that feeds Gemini review comments and CI workflow results back into the Jules session, enabling Jules to interactively fix issues in Pull Requests.

## Overview

The goal is to create a closed loop where:
1.  Jules creates a PR.
2.  CI runs and/or Gemini Review runs.
3.  If checks fail or changes are requested, a task is triggered for Jules.
4.  Jules receives the feedback (logs + comments) and attempts to fix the PR.

## Components

### 1. Feedback Logic Script (`scripts/feed_jules_feedback.py`)

A new Python script will be created to orchestrate the feedback collection and Jules session creation. This script will be invoked by the scheduler or an event-driven workflow.

**Responsibilities:**
-   **Discovery**: Identify open Pull Requests where the author is `jules-bot` (or the configured Jules user).
-   **Analysis**:
    -   Check the status of the latest CI workflow run for the PR's head branch.
    -   Fetch recent comments on the PR, specifically looking for reviews from the Gemini bot or "NEEDS CHANGES" reviews.
    -   Determine if the PR needs attention (e.g., CI failed, or unaddressed negative feedback since the last commit).
-   **Action**:
    -   If attention is needed, construct a prompt context containing:
        -   The CI failure logs (snippet).
        -   The content of the Gemini review (recommendations).
        -   Links to the PR and relevant runs.
    -   Call `JulesClient.create_session` to start a new session on the existing branch.
    -   Prompt Template: "Your PR #{number} has received feedback. CI Status: {status}. Review: {review_summary}. Please fix the issues."

### 2. Scheduler Integration (`.github/workflows/jules_scheduler.yml`)

We will integrate the feedback script into the existing scheduler workflow. This ensures that Jules periodically checks his active work for feedback without requiring complex event triggers for every possible CI state.

**Changes:**
-   Add a new step (or a separate job) in `jules_scheduler.yml` that runs `scripts/feed_jules_feedback.py`.
-   Ensure the job has `pull-requests: read/write` and `actions: read` permissions to fetch CI status and comments.

### 3. Prompt Template

A new prompt template (or constructed string in the script) will be designed to effectively communicate the errors to Jules.

**Structure:**
```markdown
# Task: Fix Pull Request #{pr_number}

Your Pull Request "{pr_title}" has encountered issues.

## CI Status: {ci_status}
{ci_logs_snippet}

## Code Review Feedback
{review_comments}

## Instructions
1. Analyze the errors and feedback above.
2. Modify the code in the current branch to resolve these issues.
3. Commit and push your changes.
```

## Implementation Steps

1.  **Create `scripts/feed_jules_feedback.py`**:
    -   Implement `find_jules_prs()` using `gh` CLI or `PyGithub` (available via `uv`).
    -   Implement `get_ci_status(pr)` and `get_review_feedback(pr)`.
    -   Implement `trigger_jules_fix(pr, feedback)`.
    -   Use `JulesClient` (from `.claude/skills/jules-api`) to initiate the session.

2.  **Update `jules_scheduler.yml`**:
    -   Add the execution of the feedback script to the `tick` job or a new `feedback` job.

3.  **Testing**:
    -   Manually trigger the feedback script on a known broken PR to verify it correctly identifies the issue and creates a Jules session.

## Considerations

-   **Loop Prevention**: The script should verify that Jules hasn't already just committed a "fix" that is currently running in CI. It should only trigger if the *latest* CI run has finished and failed.
-   **Concurrency**: Ensure we don't spawn multiple fix sessions for the same PR simultaneously. `JulesClient` creates a session; we might need to check if one is already active (if the API supports it) or rely on the fact that the scheduler runs periodically (e.g., hourly).
-   **Cost Control**: Limit the number of automatic fix attempts per PR (e.g., max 3) to prevent burning credits on unfixable issues. This can be tracked via a hidden comment on the PR or by counting commits.

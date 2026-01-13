# RFC: GitHub Issue Integration
**Status:** Actionable Proposal
**Date:** 2026-01-15
**Disruption Level:** Medium - Fast Path

## 1. The Vision
This proposal introduces a new, optional "Action Dispatcher" to the Egregora pipeline. After the `DecisionExtractionAgent` identifies action items, this dispatcher will connect to the GitHub API and automatically create a new issue in a designated repository. The issue title will be the action item, the body will contain a link back to the source blog post, and it can be automatically assigned to a specific user.

## 2. The Broken Assumption
This proposal breaks the assumption that **Egregora's output lives only within its own ecosystem (the blog).**

> "We currently assume that the value of extracted knowledge is for passive review. This proposal asserts that the value is in actively pushing that knowledge into the systems where work actually happens."

This is the first step in transforming Egregora from a system of record into a system of engagement.

## 3. The First Implementation Path (≤30 days)
- **Create a `GitHubActionDispatcher` class**: This class will be responsible for connecting to the GitHub API (using a personal access token stored in `.egregora.toml`).
- **Add a new configuration section**: The `.egregora.toml` file will get a new `[dispatcher.github]` section to specify the repository, default assignee, and API token.
- **Integrate into the orchestration pipeline**: After the enrichment step, the main pipeline will check if the GitHub dispatcher is configured. If so, it will pass the list of extracted `ActionItem` objects to the dispatcher.
- **Error Handling**: The dispatcher must have robust error handling to prevent pipeline failures due to API issues or misconfiguration.

## 4. The Value Proposition
This is the fastest and most direct way to make the "Decision Ledger" moonshot useful. It takes the abstract concept of an "action item" and makes it a tangible, trackable GitHub issue in seconds. This provides immense, immediate value to any development team using Egregora. Critically, it forces us to build the first real "write" integration, creating the muscle and patterns needed for the broader API vision without boiling the ocean.

## 5. Success Criteria
- A new `GitHubActionDispatcher` is implemented and tested.
- When configured, Egregora successfully creates GitHub issues from extracted action items.
- The feature is disabled by default and can be enabled via `.egregora.toml`.
- The integration is documented for users.

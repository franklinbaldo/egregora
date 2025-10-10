# Issue #017: Implement `egregora init` Interactive Setup Wizard

- **Status**: Proposed
- **Type**: UX Enhancement
- **Priority**: High
- **Effort**: Medium

## Problem

New users currently bootstrap their configuration by copying `egregora.toml.example` and manually pruning it. The file is long, covers advanced scenarios, and is intimidating for first runs. This friction was captured in `dev/issues/002-configuration-ux.md`, and there is still no streamlined path to generate a minimal configuration.

## Proposal

1. **Add a Typer command.** Introduce `egregora init`, using `typer` for prompts and `rich` for friendly output.
2. **Guide through essentials.** Ask for the minimum viable configuration: WhatsApp ZIP directory, output posts directory, and optional Gemini API key (with a `--demo-mode` flag to skip).
3. **Generate a trimmed config.** Write a minimal `egregora.toml` with comments pointing to the example file for advanced options.
4. **Document the workflow.** Update the quickstart and configuration docs to highlight the wizard.
5. **Future-proof.** Structure the command so additional questions can be toggled on with a `--advanced` flag later.

## Expected Benefits

- Lowers the barrier to the first successful run.
- Reduces manual editing errors in configuration files.
- Reinforces the onboarding narrative established in the developer UX issue.

## Dependencies

- Requires alignment with planned demo mode work (issue #001) to ensure consistent messaging.
- Any telemetry or analytics decisions should account for configuration defaults created by the wizard.

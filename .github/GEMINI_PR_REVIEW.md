# Automated PR Code Review with Gemini

This repository uses an automated code review system powered by Google's Gemini AI to provide comprehensive, candid feedback on every pull request. The PR review workflow now performs three tasks in a **single Gemini invocation**: (1) code review comment, (2) merge gating decision, and (3) optional PR title/description rewrite. Everything runs through the same `google-github-actions/run-gemini-cli@v0` runner for consistent authentication, diagnostics, and model selection.

## Runner & Model Routing

- **Shared runner:** All Gemini tasks (review, merge decision, PR rewrite) invoke the same runner so failures, diagnostics, and logging behave consistently.
- **Default model chains:**
  - **PR review pipeline (review + merge decision + rewrite):** `gemini-3-pro-preview` → `gemini-3-flash-preview` → `gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.5-flash-lite` (fallback order).
  - **Overriding models:** Adjust the `gemini_model` inputs in the workflow or wire them to repository variables/workflow inputs for per-repo or per-run overrides. The merge decision uses the same call/output as the review.
- **Retired workflows:** Separate merge-gate and PR-rewriter workflows have been removed; their functionality now rides on the PR review workflow output.

## Trigger Modes

The workflow can be triggered in two ways:

### 1. Automatic Mode
Runs automatically when a PR is opened, synchronized, reopened, or marked as ready for review (draft PRs are skipped).

### 2. On-Demand Mode (via Comment)
Comment on any PR with `@gemini {your specific request}` to trigger a custom review.

**Examples:**
- `@gemini Please focus on security vulnerabilities`
- `@gemini Review the performance implications of these changes`
- `@gemini Check if this follows our architectural patterns`
- `@gemini` (for a standard comprehensive review)

## How It Works

1. **Trigger**: The workflow activates either automatically (PR events) or on-demand (via `@gemini` comment).

2. **Security Check** (comment-triggered only): For `@gemini` comments, verifies that either:
   - The PR is from the same repository, OR
   - The comment author is a repository collaborator
   - This prevents malicious code execution from untrusted fork PRs

3. **Validation**: The workflow checks that `GEMINI_API_KEY` is configured and exits immediately if not, before running any expensive operations.

4. **Context Collection**:
   - Checks out the repository with full history
   - Fetches the PR's unified diff via `git diff`
   - Extracts PR description and commit messages
   - Reads CLAUDE.md for project-specific patterns

5. **AI Review** (Two-Phase Approach):

   **Phase 1: Understanding & Steel-Manning**
   - Analyzes the actual code changes (PRIMARY source of truth)
   - Reads stated intent from PR description and commits (SECONDARY - may be incomplete)
   - Reconciles any gaps between stated and actual intent
   - Steel-mans the author's approach (strongest interpretation)
   - Defines success criteria for the PR

   **Phase 2: Critical Evaluation**
   - Evaluates correctness against objectives
   - Assesses implementation quality
   - Flags critical issues (privacy, security, bugs)
   - Suggests improvements that still meet objectives
   - Checks egregora pattern compliance

6. **Comment Posting**:
   - Posts the review as a comment on the PR
   - Automatically splits long reviews into multiple comments if needed
   - Indicates which Gemini model was used
   - Supplies a JSON payload with:
     - `review_comment` (markdown for the PR comment)
     - `merge` + `merge_reason` + `merge_risk` (used to gate merges)
     - `pr_title` and `pr_body` (optional rewrites applied automatically)

## Configuration

### Required Secrets & Variables

Add these under **Settings → Secrets and variables → Actions**:

- **Secret:** `GEMINI_API_KEY` — required for the Gemini review workflow.
- **Variable:** `GEMINI_MODEL` — optional; overrides the first model in the chain (defaults to `gemini-3-pro-preview` when unset).

To change model order, update the `gemini_model` values in `.github/workflows/gemini-pr-review.yml` or bind them to workflow inputs/repository variables so operators can override without code changes.

## Customizing Repomix Output

The `.repomixignore` file controls which files are excluded from the repository bundle. This helps reduce noise and focus the review on relevant code.

Current exclusions include:
- Documentation directories
- Test directories
- Build artifacts and dependencies
- Version control files
- Environment files and secrets
- IDE configuration
- Binary and media files

You can modify `.repomixignore` to adjust what gets included in the review context.

## Review Style & Expertise

Gemini's code review approach emphasizes:

### Understanding First, Critique Second
- **Code-first analysis** - infers intent from actual changes (the primary source of truth)
- **Steel-manning** - presents the STRONGEST interpretation of the author's choices before criticizing
- **Context reconciliation** - acknowledges that PR descriptions and commit messages are often incomplete
- **Objective-based evaluation** - judges implementation against stated/inferred goals, not ideal perfection

### Review Quality
- **Concise but complete** - every sentence adds value, no verbose explanations
- **Ruthlessly prioritized** - critical issues first, minor style points last (or omitted)
- **Direct and candid** - points out real issues without sugar-coating
- **Professional & empathetic** - constructive criticism, assumes good faith, not personal attacks
- **Specific and actionable** - cites exact locations (file:line), provides implementable suggestions
- **Focused on substance** - skips obvious points, avoids unnecessary praise or preamble

When triggered via `@gemini` comments, Gemini focuses on your specific request while remaining contextually aware of what has already been discussed in the PR.

## The Two-Phase Review Philosophy

### Why Code-First Understanding Matters

Traditional code reviews often jump straight to finding issues, which can lead to:
- ❌ Flagging intentional design decisions as "mistakes"
- ❌ Missing the context and constraints the author faced
- ❌ Providing feedback that doesn't align with the PR's actual goals
- ❌ Creating adversarial dynamics instead of collaborative improvement

**Our approach:** Understand FIRST, critique SECOND.

### Phase 1: Understanding & Steel-Manning

The reviewer **must** first understand what the PR is trying to accomplish by:

1. **Reading the actual code changes** (PRIMARY source)
   - What files changed? What patterns emerge?
   - What do function names, imports, and structure tell us?
   - What will this code actually DO when executed?

2. **Reading PR description and commits** (SECONDARY - often incomplete)
   - ⚠️ **Key insight:** PR descriptions and commit messages are frequently vague, incomplete, or missing
   - We treat them as hints, not gospel

3. **Reconciling and steel-manning**
   - Does stated intent match actual changes?
   - If there's a gap, what's the STRONGEST interpretation of the code?
   - What legitimate constraints might justify this approach?

4. **Defining success criteria**
   - What does "working correctly" mean for THIS PR?
   - What are the primary vs. secondary objectives?

### Phase 2: Critical Evaluation

Only AFTER understanding the intent, the reviewer evaluates:

- **Correctness:** Does it achieve its objectives?
- **Implementation quality:** Is the approach sound? Are there better alternatives?
- **Safety:** Privacy, security, performance issues
- **Patterns:** Does it follow egregora conventions?

### Example: Before vs. After

**❌ Old approach (critique-first):**
> **file.py:45** - You're using a dict instead of a Pydantic model. This is inconsistent with our patterns and should be changed.

**✅ New approach (understand-first):**
> **🎯 Intent & Context:**
> The code changes suggest this is optimizing a hot path by avoiding Pydantic validation overhead. The stated intent mentions "performance improvements" but doesn't specify where.
>
> **Steel-man interpretation:** The author identified that Pydantic validation was a bottleneck in this specific code path and chose raw dicts for speed.
>
> **⚠️ Implementation Quality:**
> While the performance goal is valid, consider:
> - Is this actually a hot path? (Add benchmark data to PR description)
> - Could we use `model_config = ConfigDict(validate_assignment=False)` to get type hints without runtime overhead?
> - Document the performance rationale in a comment for future maintainers

The second approach:
- ✅ Acknowledges the author's legitimate goal
- ✅ Validates whether the solution fits the problem
- ✅ Suggests alternatives that STILL meet the performance objective
- ✅ Feels collaborative, not adversarial

### Review Output Structure

Every review follows this structure:

```markdown
### 🎯 Intent & Context (Phase 1)
**What the code actually does:** [2-3 sentences from diff analysis]
**Stated intent:** [1 sentence from PR/commits, or "No description provided"]
**Reconciliation:** Does stated match actual? [YES/NO/PARTIAL]
**Steel-man interpretation:** [Strongest case for this approach]
**Success criteria:** [Primary objectives 1, 2, ...]

### ✅ Does It Achieve Its Goals? (Phase 2 Correctness)
- Objective 1: [✅/❌/⚠️] Brief explanation
- Objective 2: [✅/❌/⚠️] Brief explanation

### 🔍 Critical Issues (Phase 2 Safety)
[Privacy, security, bugs - empty if none]

### ⚠️ Implementation Quality (Phase 2)
[Architecture, patterns, simplicity - with alternatives that still meet goals]

### 💡 Suggestions (Phase 2)
[Nice-to-haves that don't block merging]

### 🏗️ Egregora Patterns Compliance
- Privacy-first: [✅/❌/N/A]
- Ibis over pandas: [✅/❌/N/A]
- [etc.]

### ✅ Final Verdict
- Ready to merge: [YES/NO/WITH CHANGES]
- Top priority action: [Most important next step]
```

## Usage Examples

### Automatic Review (Default)
Simply open, update, or mark your PR as ready for review. Gemini will automatically provide a comprehensive code review.

### Targeted Review (via Comment)
Ask Gemini to focus on specific aspects by commenting on the PR:

```
@gemini Please review the error handling in the new authentication module
```

```
@gemini Focus on potential SQL injection vulnerabilities
```

```
@gemini Analyze the time complexity of the new sorting algorithm
```

```
@gemini Check if the API changes are backwards-compatible
```

```
@gemini Review the test coverage for edge cases
```

The text after `@gemini` becomes part of the prompt, directing Gemini to focus on your specific concerns while still applying its full code review expertise.

## Security

### Fork PR Protection
**CRITICAL:** The workflow implements protection against malicious fork PRs:

When triggered via `@gemini` comments:
- If the PR is from the **same repository**: workflow runs normally
- If the PR is from a **fork**: the workflow checks if the comment author is a repository collaborator
  - **Collaborators**: Review proceeds normally
  - **Non-collaborators**: Workflow exits immediately with a security error

**Why this matters:** Without this protection, an attacker could:
1. Fork the repository
2. Modify `.github/scripts/gemini-pr-review.js` with malicious code
3. Open a PR with the malicious changes
4. Comment `@gemini` to trigger the workflow
5. Execute arbitrary code with access to `GEMINI_API_KEY`

The collaborator check prevents this attack vector while still allowing trusted team members to trigger reviews on fork PRs.

### Input Sanitization
The workflow safely handles user-controlled input from `@gemini` comments to prevent code injection:
- All GitHub context values are passed through environment variables
- Comment body extraction uses Python (not shell substitution) to prevent command injection
- No user input is directly interpolated into shell commands

### Permissions
The workflow requires these permissions:
- `contents: read` - To checkout the repository
- `pull-requests: write` - To post review comments

### Best Practices
- The workflow validates `GEMINI_API_KEY` before running expensive operations
- Artifacts are uploaded for debugging but expire after 7 days
- The workflow runs in the PR head context, not the base branch

## Artifacts

For debugging purposes, the workflow uploads artifacts containing:
- `repomix.txt` - The full repository bundle
- `pr.patch` - The PR changes in patch format
- `pr-comments.json` - The complete PR conversation

These are retained for 7 days and can be downloaded from the workflow run page.

## Model Selection

- **gemini-3-pro-preview**: Highest-quality default (first in the fallback chain).
- **gemini-3-flash-preview**: Fastest 3.x fallback.
- **gemini-2.5-pro**: First 2.5-tier fallback when 3.x is unavailable.
- **gemini-2.5-flash**: Fast 2.5-tier fallback.
- **gemini-2.5-flash-lite**: Lowest-cost fallback.

You can change the model order by editing the `gemini_model` values (or variable bindings) in `.github/workflows/gemini-pr-review.yml`. Consider wiring workflow inputs or repo variables if operators need per-run overrides without code changes.

## Troubleshooting

### Shared Diagnostics

- **Missing secrets:** The runner exits early with `GEMINI_API_KEY` missing—set the secret and re-run.
- **Quota/availability:** Fallback chains (where configured) try the next model; if all fail, expect a diagnostic PR comment with the model sequence attempted.
- **Timeouts/context:** Very large diffs or patches may hit context limits; check for truncation notices in artifacts/comments.
- **Model overrides:** Ensure the intended repository variable/input is set before rerunning when overriding the model list.

### Review not appearing

1. Check that the PR is not in draft mode.
2. Verify `GEMINI_API_KEY` is configured.
3. Review the workflow run logs in the Actions tab for error messages and which models were attempted.
4. Confirm the chosen model (default or overridden) is available and within quota.

### Review is incomplete

- Long outputs post as multiple comments; scan the PR thread.
- Check the uploaded artifacts (diff, patch) to confirm what was sent to Gemini.
- If a model override was applied, ensure it supports the context size of the PR.

### API Rate Limits

- Gemini rate limits depend on your API tier.
- Prefer `gemini-2.5-flash`/`gemini-2.5-flash-lite` for higher throughput when Pro quota is constrained.
- Upgrade quota in Google AI Studio if throttling persists.

## Workflow Files

- **Workflow**: `.github/workflows/gemini-pr-review.yml`
- **Script**: `.github/scripts/gemini-pr-review.js`
- **Config**: `.repomixignore`

## Future Enhancements

Potential improvements:
- Support for review comments on specific lines (vs. general PR comments)
- Incremental reviews (only review changed files in subsequent pushes)
- Custom prompt templates via configuration file
- Integration with PR checks/status
- Cost tracking and reporting
- Multiple AI model comparison

# Automated PR Code Review with Gemini

This repository uses an automated code review system powered by Google's Gemini AI to provide comprehensive, candid feedback on every pull request.

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

## Configuration

### Required Secrets

Add the following secret to your repository (Settings → Secrets and variables → Actions):

- **`GEMINI_API_KEY`**: Your Google Gemini API key
  - Get one at: https://makersuite.google.com/app/apikey

### Optional Variables

You can customize the Gemini model by setting a repository variable:

- **`GEMINI_MODEL`**: The Gemini model to use (default: `gemini-3-pro-preview`)
  - Available models: `gemini-3-pro-preview`, `gemini-1.5-pro-002`, `gemini-1.5-flash-latest`, etc.
  - Legacy values such as `gemini-1.5-flash` and `gemini-flash-latest` are automatically mapped to the supported default, and the script automatically adds the `models/` prefix if omitted.
  - Set at: Settings → Secrets and variables → Actions → Variables

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

- **gemini-3-pro-preview** (default): Newest Pro reasoning model with the best code understanding
- **gemini-1.5-pro-002**: Thorough analysis for complex changes
- **gemini-1.5-flash-latest**: Fast, cost-effective option when Pro is unnecessary

You can change the model by setting the `GEMINI_MODEL` repository variable.

## Troubleshooting

### Review not appearing

1. Check that the PR is not in draft mode
2. Verify `GEMINI_API_KEY` secret is set correctly - the workflow will fail immediately with a clear error message if not configured
3. Check the workflow run logs in the Actions tab for detailed error messages
4. Ensure the API key has sufficient quota

### Review is incomplete

- If the review is very long, it will be split into multiple comments
- Check for additional comments from the GitHub Actions bot
- Review the workflow artifacts to see the full context sent to Gemini

### API Rate Limits

- Gemini has rate limits based on your API tier
- Consider using `google-gla:gemini-flash-latest` for higher throughput
- Or upgrade your Gemini API quota at https://console.cloud.google.com/

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

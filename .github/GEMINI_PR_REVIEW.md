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
   - Runs `npx repomix` to generate a complete textual bundle of the codebase (`repomix.txt`)
   - Fetches the PR's `.patch` file via GitHub API
   - Fetches the entire PR conversation (all comments) for context

5. **AI Review**:
   - Sends repository context, PR changes, and conversation history to Gemini
   - Gemini considers what has already been discussed to avoid repetition
   - In automatic mode: Provides a concise but complete review focusing on what matters most
   - In comment mode: Addresses your specific request while being contextually aware
   - Review skills include:
     - Summary and overall assessment
     - Correctness & bugs
     - API/contracts & backwards-compatibility
     - Security & privacy concerns
     - Performance & complexity
     - Testing & observability
     - Style & readability
     - Architecture/design trade-offs
     - Actionable checklist

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

- **`GEMINI_MODEL`**: The Gemini model to use (default: `gemini-flash-latest`)
  - Available models: `gemini-flash-latest`, `gemini-1.5-pro-002`, etc.
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
- **Concise but complete** - every sentence adds value, no verbose explanations
- **Contextually aware** - considers existing PR conversation to avoid repetition
- **Ruthlessly prioritized** - critical issues first, minor style points last
- **Direct and candid** - points out real issues without sugar-coating
- **Professional** - constructive criticism, not personal attacks
- **Specific and actionable** - cites exact locations (file:line), provides implementable suggestions
- **Focused on substance** - skips obvious points, avoids unnecessary praise or preamble

When triggered via `@gemini` comments, Gemini focuses on your specific request while remaining contextually aware of what has already been discussed in the PR.

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

- **gemini-flash-latest** (default): Fast, cost-effective, good for most PRs - always uses the latest Flash model
- **gemini-1.5-pro-002**: More thorough analysis, better for complex changes
- **gemini-1.5-flash-8b**: Lightweight option for simple PRs

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

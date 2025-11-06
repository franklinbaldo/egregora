# Automated PR Code Review with Gemini

This repository uses an automated code review system powered by Google's Gemini AI to provide comprehensive, candid feedback on every pull request.

## How It Works

1. **Trigger**: The workflow runs automatically when a PR is opened, synchronized, reopened, or marked as ready for review (draft PRs are skipped).

2. **Validation**: The workflow first checks that `GEMINI_API_KEY` is configured and exits immediately if not, before running any expensive operations.

3. **Context Collection**:
   - Checks out the repository with full history
   - Runs `npx repomix` to generate a complete textual bundle of the codebase (`repomix.txt`)
   - Fetches the PR's `.patch` file via GitHub API

4. **AI Review**:
   - Sends both the repository context and PR changes to Gemini
   - Gemini analyzes the code and provides a structured review covering:
     - Summary and overall assessment
     - Correctness & bugs
     - API/contracts & backwards-compatibility
     - Security & privacy concerns
     - Performance & complexity
     - Testing & observability
     - Style & readability
     - Architecture/design trade-offs
     - Actionable checklist

5. **Comment Posting**:
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

## Review Tone

The AI reviewer is configured to be:
- **Direct and candid** - points out real issues without sugar-coating
- **Professional** - constructive criticism, not personal attacks
- **Specific** - cites exact locations when possible
- **Actionable** - provides concrete suggestions
- **Focused on substance** - avoids unnecessary praise or flattery
- **Prioritized** - distinguishes critical issues from minor improvements

## Artifacts

For debugging purposes, the workflow uploads artifacts containing:
- `repomix.txt` - The full repository bundle
- `pr.patch` - The PR changes in patch format

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
- Consider using `gemini-1.5-flash-8b` for higher throughput
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

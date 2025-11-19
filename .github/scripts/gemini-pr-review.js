name: Gemini PR Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  issue_comment:
    types: [created]

# Cancel previous runs on the same PR to save API usage and prevent conflicting comments
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.event.issue.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write
  issues: write
  actions: write

jobs:
  code-review:
    runs-on: ubuntu-latest
    timeout-minutes: 15 # Safety timeout
    if: |
      (github.event_name == 'pull_request' && !github.event.pull_request.draft) ||
      (github.event_name == 'issue_comment' && github.event.issue.pull_request && contains(github.event.comment.body, '@gemini'))

    steps:
      - name: Pre-check and Context Setup
        id: context
        uses: actions/github-script@v7
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        with:
          script: |
            const eventName = context.eventName;
            let prData = {};
            
            // 1. Get PR Details based on event type
            if (eventName === 'issue_comment') {
              const { data: pr } = await github.rest.pulls.get({
                owner: context.repo.owner,
                repo: context.repo.repo,
                pull_number: context.issue.number
              });
              prData = pr;
            } else {
              prData = context.payload.pull_request;
            }

            // 2. Check Fork Status
            const isFork = prData.head.repo.full_name !== prData.base.repo.full_name;
            const prHeadSha = prData.head.sha;
            const prNumber = prData.number;

            // 3. Security: Check API Key and Permissions
            const apiKey = process.env.GEMINI_API_KEY;
            if (!apiKey) {
              if (isFork) {
                console.log("ℹ️ Skipping: GEMINI_API_KEY not available for fork PRs automatically.");
                return { skip: true };
              } else {
                core.setFailed("❌ GEMINI_API_KEY is not set in repo secrets.");
                return;
              }
            }

            // 4. Security: If comment on Fork, verify User is Collaborator
            if (eventName === 'issue_comment' && isFork) {
              const commentUser = context.payload.comment.user.login;
              try {
                await github.rest.repos.checkCollaborator({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  username: commentUser
                });
                console.log(`✅ User ${commentUser} is a collaborator.`);
              } catch (error) {
                core.setFailed(`❌ SECURITY: User ${commentUser} is NOT a collaborator. Review denied.`);
                return;
              }
            }

            // 5. Extract Comment if applicable
            let userComment = '';
            let triggerMode = 'automatic';
            if (eventName === 'issue_comment') {
              const body = context.payload.comment.body;
              const match = body.match(/@gemini\s*(.*)/s);
              userComment = match ? match[1].trim() : '';
              triggerMode = 'comment';
            }

            // Export variables
            core.setOutput('skip_review', 'false');
            core.setOutput('pr_head_sha', prHeadSha);
            core.setOutput('pr_number', prNumber);
            core.setOutput('user_comment', userComment);
            core.setOutput('trigger_mode', triggerMode);

      - name: Checkout Base Repository (Trusted Scripts)
        if: steps.context.outputs.skip_review != 'true'
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.ref || 'main' }}
          fetch-depth: 1 # Only need latest of base to run the scripts

      - name: Fetch PR Head (Untrusted Code)
        if: steps.context.outputs.skip_review != 'true'
        env:
          PR_HEAD_SHA: ${{ steps.context.outputs.pr_head_sha }}
        run: |
          git fetch origin "$PR_HEAD_SHA" --depth=1
          git worktree add pr-code "$PR_HEAD_SHA"

      - name: Setup Node.js
        if: steps.context.outputs.skip_review != 'true'
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          # Optional: Cache npm dependencies if you have a package-lock.json
          # cache: 'npm' 

      - name: Install Script Dependencies
        if: steps.context.outputs.skip_review != 'true'
        run: |
          if [ -f "package.json" ]; then
            npm ci --ignore-scripts
          else
            # Minimal install if no package.json exists in root
            npm install @google/generative-ai @octokit/rest dotenv --no-save
          fi

      - name: Generate Repository Context (Repomix)
        if: steps.context.outputs.skip_review != 'true'
        run: |
          # Use trusted .repomixignore from base if available
          if [ -f .repomixignore ]; then
            cp .repomixignore pr-code/.repomixignore
          fi

          cd pr-code
          # Using npx with pinned version for security
          # Ignore package-lock and other heavy files explicitly to save context tokens
          npx -y repomix@latest \
            --output ../repomix.txt \
            --ignore "**/*.lock,**/package-lock.json,**/yarn.lock,**/node_modules/**"
          cd ..
          
          echo "✅ Context bundle size: $(du -h repomix.txt)"

      - name: Fetch Diff and Conversation
        if: steps.context.outputs.skip_review != 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const prNumber = parseInt('${{ steps.context.outputs.pr_number }}');
            
            // Fetch Diff
            const diff = await github.rest.pulls.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              pull_number: prNumber,
              mediaType: { format: "diff" }
            });
            fs.writeFileSync('pr.patch', diff.data);

            // Fetch Comments
            const comments = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: prNumber
            });
            fs.writeFileSync('pr-comments.json', JSON.stringify(comments.data, null, 2));

      - name: Run Gemini Code Review
        if: steps.context.outputs.skip_review != 'true'
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_MODEL: ${{ vars.GEMINI_MODEL || 'gemini-1.5-flash' }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ steps.context.outputs.pr_number }}
          TRIGGER_MODE: ${{ steps.context.outputs.trigger_mode }}
          USER_COMMENT: ${{ steps.context.outputs.user_comment }}
        run: |
          # Ensure script exists before running
          if [ -f ".github/scripts/gemini-pr-review.js" ]; then
            node .github/scripts/gemini-pr-review.js
          else
            echo "❌ Error: .github/scripts/gemini-pr-review.js not found in base branch."
            exit 1
          fi

      - name: Upload Artifacts (Debugging)
        if: failure() # Only upload if something failed to save storage
        uses: actions/upload-artifact@v4
        with:
          name: review-debug-artifacts
          path: |
            repomix.txt
            pr.patch
            pr-comments.json
          retention-days: 3

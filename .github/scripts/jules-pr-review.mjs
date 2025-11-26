#!/usr/bin/env node
/**
 * Jules automated PR review script for egregora
 *
 * This script:
 * 1. Finds the egregora repo in Jules sources
 * 2. Starts a Jules session to review the current PR
 * 3. Polls for completion and extracts the review
 * 4. Posts the review as a PR comment
 */

import fs from "node:fs";
import { Octokit } from "@octokit/rest";

const JULES_API_BASE = "https://jules.googleapis.com/v1alpha";
const POLL_INTERVAL_MS = 5000;
const MAX_POLL_ATTEMPTS = 120; // 10 minutes max

// Egregora-specific review prompt
const EGREGORA_REVIEW_PROMPT = `
Review this pull request for the egregora repository.

## Context
Egregora is a privacy-first AI pipeline that extracts structured knowledge from unstructured communication. Key principles:
- **Privacy-First:** Anonymize BEFORE LLM (critical invariant)
- **Ibis Everywhere:** DuckDB tables, pandas only at boundaries
- **Functional Transforms:** Table → Table (no classes)
- **Alpha Mindset:** Clean breaks over backward compatibility

## Architecture
Three-layer functional architecture:
- Layer 3: orchestration/ (high-level workflows)
- Layer 2: transformations/, input_adapters/, output_adapters/, database/
- Layer 1: data_primitives/ (foundation models)

## Review Focus
1. **Privacy & Security:**
   - Privacy stage runs BEFORE any LLM processing
   - No PII leaks to external APIs
   - Proper UUID-based anonymization

2. **Code Quality:**
   - Line length: 110 chars max
   - Ruff compliance (no BLE001, proper exception handling)
   - Type hints where appropriate
   - Proper error propagation (avoid blanket except Exception)

3. **Architecture Compliance:**
   - Input/output adapters implement correct protocols (InputAdapter, OutputAdapter)
   - Pure functional transforms (Table → Table)
   - Schema validation with validate_ir_schema() where needed
   - IR_MESSAGE_SCHEMA columns preserved

4. **Testing:**
   - Unit tests for new functionality
   - Integration tests with VCR cassettes for API calls
   - Tests pass in CI (--retrieval-mode=exact for RAG without VSS)

5. **Documentation:**
   - Breaking changes documented in CLAUDE.md
   - Docstrings for public APIs
   - Clear commit messages

6. **Patterns to Watch:**
   - Don't bypass privacy stage
   - Don't use pandas directly (use Ibis)
   - Don't modify IR_MESSAGE_SCHEMA without migration plan
   - Use VectorStore facade for RAG operations
   - Config goes in .egregora/config.yml, not hardcoded

## Output Format
Provide a concise markdown review with:
- **Summary:** High-level assessment (1-2 sentences)
- **Issues:** List of concrete problems with file:line references
- **Suggestions:** Specific code improvements (inline snippets where helpful)
- **Approval:** ✅ LGTM / ⚠️ Minor issues / ❌ Needs work

Keep it actionable and specific. Reference egregora conventions where relevant.
`.trim();

class JulesAPIError extends Error {
  constructor(message, response) {
    super(message);
    this.name = "JulesAPIError";
    this.response = response;
  }
}

async function julesAPICall(endpoint, options = {}) {
  const url = `${JULES_API_BASE}${endpoint}`;
  const headers = {
    "X-Goog-Api-Key": process.env.JULES_API_KEY,
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorText = await response.text();
    throw new JulesAPIError(
      `Jules API error: ${response.status} ${response.statusText}`,
      { status: response.status, body: errorText }
    );
  }

  return response.json();
}

async function findEgregoraSource(owner, repo) {
  console.log(`🔍 Looking for Jules source: ${owner}/${repo}`);

  const data = await julesAPICall("/sources");
  const sources = data.sources || [];

  const source = sources.find(s =>
    s.githubRepo?.owner === owner && s.githubRepo?.repo === repo
  );

  if (!source) {
    console.error("❌ Repository not found in Jules sources.");
    console.error("Available sources:", sources.map(s => s.name).join(", "));
    throw new Error(
      `Repo ${owner}/${repo} not registered as a Jules source. ` +
      `Please connect the repo at https://jules.google.com/`
    );
  }

  console.log(`✅ Found source: ${source.name}`);
  return source;
}

async function startReviewSession(sourceName, prBranch, prNumber) {
  console.log(`🚀 Starting Jules review session for PR #${prNumber} on branch ${prBranch}`);

  const data = await julesAPICall("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: `PR #${prNumber} automated review`,
      prompt: EGREGORA_REVIEW_PROMPT,
      sourceContext: {
        source: sourceName,
        githubRepoContext: {
          startingBranch: prBranch,
        },
      },
    }),
  });

  console.log(`✅ Session created: ${data.id}`);
  return data;
}

async function pollForReview(sessionId) {
  console.log(`⏳ Polling for review completion (max ${MAX_POLL_ATTEMPTS * POLL_INTERVAL_MS / 1000}s)...`);

  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
    const data = await julesAPICall(`/sessions/${sessionId}/activities?pageSize=50`);
    const activities = data.activities || [];

    // Look for review-related activities
    const reviewActivity = activities.find(a =>
      a.progressUpdated?.title?.toLowerCase().includes("review") ||
      a.progressUpdated?.title?.toLowerCase().includes("code") ||
      a.progressUpdated?.description?.toLowerCase().includes("review")
    );

    if (reviewActivity && reviewActivity.progressUpdated?.description) {
      console.log(`✅ Review found: ${reviewActivity.progressUpdated.title}`);
      return reviewActivity.progressUpdated.description;
    }

    // Check if session completed
    const completed = activities.some(a => a.sessionCompleted);
    if (completed) {
      // Grab last meaningful progress update as fallback
      const lastProgress = activities
        .filter(a => a.progressUpdated?.description)
        .pop();

      if (lastProgress) {
        console.log(`✅ Session completed, using last progress update`);
        return lastProgress.progressUpdated.description;
      }

      console.warn("⚠️ Session completed but no review content found");
      return "Jules completed the review session but did not return specific feedback.";
    }

    // Log progress
    if (attempt % 6 === 0) { // Every 30 seconds
      const latestActivity = activities[0];
      if (latestActivity?.progressUpdated?.title) {
        console.log(`  Progress: ${latestActivity.progressUpdated.title}`);
      }
    }

    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(`Timeout: No review received after ${MAX_POLL_ATTEMPTS} attempts`);
}

async function postReviewComment(octokit, owner, repo, prNumber, reviewText) {
  console.log(`💬 Posting review to PR #${prNumber}`);

  const commentBody = `### 🤖 Jules Automated Review

${reviewText}

---
<sub>Powered by [Jules](https://jules.google/) | [Skip this check](https://github.com/${owner}/${repo}/blob/main/.github/workflows/jules-pr-review.yml) by adding \`[skip-jules]\` to PR title</sub>`;

  await octokit.issues.createComment({
    owner,
    repo,
    issue_number: prNumber,
    body: commentBody,
  });

  console.log(`✅ Review posted successfully`);
}

async function main() {
  try {
    // Validate environment
    if (!process.env.JULES_API_KEY) {
      throw new Error("JULES_API_KEY environment variable not set");
    }
    if (!process.env.GITHUB_TOKEN) {
      throw new Error("GITHUB_TOKEN environment variable not set");
    }

    // Parse GitHub event
    const eventPath = process.env.GITHUB_EVENT_PATH;
    const event = JSON.parse(fs.readFileSync(eventPath, "utf8"));
    const prNumber = event.pull_request.number;
    const prBranch = event.pull_request.head.ref;
    const [owner, repo] = process.env.GITHUB_REPOSITORY.split("/");

    console.log(`📝 PR #${prNumber}: ${event.pull_request.title}`);
    console.log(`🌿 Branch: ${prBranch}`);

    // Initialize Octokit
    const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

    // Step 1: Find Jules source
    const source = await findEgregoraSource(owner, repo);

    // Step 2: Start review session
    const session = await startReviewSession(source.name, prBranch, prNumber);

    // Step 3: Poll for review
    const reviewText = await pollForReview(session.id);

    // Step 4: Post review
    await postReviewComment(octokit, owner, repo, prNumber, reviewText);

    console.log("✨ Jules automated review completed successfully");
    process.exit(0);

  } catch (error) {
    console.error("❌ Error during Jules PR review:");
    console.error(error.message);

    if (error instanceof JulesAPIError) {
      console.error("API Response:", error.response);
    }

    if (error.stack) {
      console.error(error.stack);
    }

    process.exit(1);
  }
}

main();

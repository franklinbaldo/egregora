#!/usr/bin/env node

const fs = require('fs');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const { Octokit } = require('@octokit/rest');

// Configuration
const MAX_CONTEXT_CHARS = 2000000; // ~500k tokens (Safety limit)
const MAX_COMMENT_LENGTH = 65000; // GitHub limit is 65536

// Environment variables
const {
  GEMINI_API_KEY,
  GEMINI_MODEL = 'gemini-1.5-flash',
  GITHUB_TOKEN,
  PR_NUMBER,
  REPO_FULL_NAME,
  TRIGGER_MODE = 'automatic',
  USER_COMMENT = ''
} = process.env;

// Validation
if (!GEMINI_API_KEY) throw new Error('Missing GEMINI_API_KEY');
if (!GITHUB_TOKEN) throw new Error('Missing GITHUB_TOKEN');

// Initialize Clients
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
const octokit = new Octokit({ auth: GITHUB_TOKEN });

/**
 * Reads a file and returns content, or empty string if missing/error
 */
function readFileSafe(path) {
  try {
    return fs.readFileSync(path, 'utf8');
  } catch (e) {
    console.warn(`⚠️ Could not read ${path}: ${e.message}`);
    return '';
  }
}

/**
 * Truncates the repository context if the total payload is too large.
 * Prioritizes the Patch and Conversation over the static Repo Context.
 */
function enforceContextLimits(repomix, patch, chat) {
  const totalSize = repomix.length + patch.length + chat.length;
  
  if (totalSize <= MAX_CONTEXT_CHARS) {
    return repomix;
  }

  console.warn(`⚠️ Total context size (${totalSize} chars) exceeds limit. Truncating repository context...`);
  
  // Calculate remaining budget for repo context
  // Keep patch and chat fully intact
  const remainingBudget = MAX_CONTEXT_CHARS - patch.length - chat.length;
  
  if (remainingBudget <= 0) {
    console.warn("⚠️ Patch is too large! Removing repository context entirely.");
    return "[Repository context omitted due to size limits - relying on patch only]";
  }

  return repomix.substring(0, remainingBudget) + "\n\n[...Truncated due to size limits...]";
}

/**
 * Generates the system prompt using XML tagging for better adherence
 */
function generatePrompt(repomix, patch, chat) {
  const userInstruction = TRIGGER_MODE === 'comment' && USER_COMMENT
    ? `The user has specifically requested: "${USER_COMMENT}". Prioritize this request.`
    : 'Provide a general code review.';

  return `
You are a senior software engineer and code reviewer.
Your task is to review a GitHub Pull Request based on the provided context.

<instructions>
1. **Tone:** Professional, concise, and actionable. No fluff.
2. **Focus:** Identify bugs, security vulnerabilities, performance issues, and breaking changes.
3. **Priority:** 
   - 🔴 CRITICAL: Bugs, security exploits, data loss.
   - 🟡 IMPORTANT: Performance, confusing logic, missing tests.
   - 🟢 MINOR: Variable naming, style preferences (mention briefly or ignore).
4. **Context:** Use the <repository_context> to understand the codebase, but focus your review on the <git_patch>.
5. **History:** Review <pr_conversation> to avoid repeating existing feedback.
6. **Input:** ${userInstruction}
</instructions>

<repository_context>
${repomix}
</repository_context>

<git_patch>
${patch}
</git_patch>

<pr_conversation>
${chat}
</pr_conversation>

<output_format>
Return the review in Markdown format.
Structure:
## 📋 Summary
(1-2 sentences)

## 🔍 Critical Issues (If any)
- **File.js:45**: Explain the bug/vuln.

## 💡 Suggestions
- **File.js:90**: Improvement logic.

## 💭 Architecture & Design
(Optional: Only if relevant)

## 🛠️ Action Items
- [ ] Fix critical bug in X
- [ ] Add tests for Y
</output_format>
`;
}

async function run() {
  console.log(`🚀 Starting review for PR #${PR_NUMBER}`);

  // 1. Read Data
  const rawRepomix = readFileSafe('repomix.txt');
  const patch = readFileSafe('pr.patch');
  const conversationRaw = readFileSafe('pr-comments.json');
  
  // 2. Format Conversation
  let conversation = "No prior conversation.";
  try {
    const comments = JSON.parse(conversationRaw);
    if (Array.isArray(comments) && comments.length > 0) {
      conversation = comments.map(c => `@${c.user.login}: ${c.body}`).join('\n---\n');
    }
  } catch (e) { /* ignore json parse errors */ }

  // 3. Budget Context
  const repomix = enforceContextLimits(rawRepomix, patch, conversation);

  console.log(`📊 Stats: Patch=${patch.length}ch, Repo=${repomix.length}ch, Chat=${conversation.length}ch`);

  // 4. Call Gemini
  const model = genAI.getGenerativeModel({ 
    model: GEMINI_MODEL,
    generationConfig: { temperature: 0.2, maxOutputTokens: 8000 }
  });

  const prompt = generatePrompt(repomix, patch, conversation);
  
  console.log("🤖 Sending to Gemini...");
  const result = await model.generateContent(prompt);
  const response = await result.response;
  const reviewText = response.text();

  console.log(`✅ Generated review (${reviewText.length} chars). Posting to GitHub...`);

  // 5. Post Comment (Handling Length Limits)
  const chunks = splitMessage(reviewText, MAX_COMMENT_LENGTH - 500); // Buffer for headers
  const [owner, repo] = REPO_FULL_NAME.split('/');

  for (let i = 0; i < chunks.length; i++) {
    const header = chunks.length > 1 ? `## 🤖 Review (Part ${i + 1}/${chunks.length})\n\n` : `## 🤖 Gemini Code Review\n\n`;
    const body = header + chunks[i] + `\n\n*Generated by ${GEMINI_MODEL}*`;

    await octokit.issues.createComment({
      owner,
      repo,
      issue_number: PR_NUMBER,
      body
    });
    
    // Avoid rate limits
    if (i < chunks.length - 1) await new Promise(r => setTimeout(r, 1000));
  }
  
  console.log("✨ Done.");
}

function splitMessage(text, maxLength) {
  const chunks = [];
  let current = "";
  
  // Split by newlines to try and keep markdown formatting intact
  const lines = text.split('\n');
  
  for (const line of lines) {
    if ((current.length + line.length) > maxLength) {
      chunks.push(current);
      current = "";
    }
    current += line + "\n";
  }
  if (current) chunks.push(current);
  return chunks;
}

run().catch(err => {
  console.error("❌ Failed:", err);
  process.exit(1);
});

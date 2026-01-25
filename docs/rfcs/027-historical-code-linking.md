# 🔭 RFC 027: Historical Code Linking

**Feature**: Historical Code Linking
**Authors**: @visionary
**Status**: Proposed
**Created**: 2026-01-22
**Moonshot**: No (Quick Win)
**Relation to Moonshot**: RFC 026 (The Universal Context Layer)

---

## 1. Problem Statement

Chat logs are full of ambiguous references to code: "Check `main.py`", "Look at the new function", "I fixed the bug in `writer.py`".

When a user reads this blog post 6 months later, `main.py` has changed completely. The context is lost. They see the file, but it doesn't match the discussion. This "Context Rot" makes the archive less valuable over time.

## 2. Proposed Solution

We will implement an **Enricher Agent Strategy** that detects file paths and Git references in the chat and converts them into **Permalinks**.

**Mechanism:**
1. **Detection**: Regex to find file paths (`src/...`, `tests/...`) and Git SHAs (`[a-f0-9]{7}`).
2. **Resolution**:
   - If a SHA is present: Link to `github.com/org/repo/blob/<SHA>/<path>`.
   - If no SHA: Use the timestamp of the message to find the *closest* Git commit in the repository history.
3. **Enrichment**: Replace the text `src/main.py` with a link `src/main.py (v1.2.3)`.

## 3. Value Proposition

- **Immediate Clarity**: Users see the exact code that was being discussed, not the current version.
- **Archive Durability**: The blog post remains accurate forever, immune to code drift.
- **Foundation for Moonshot**: This proves we can link "Chat Time" to "Code State", which is the core requirement for the Universal Context Layer (RFC 026).

## 4. BDD Acceptance Criteria

```gherkin
Feature: Historical Code Linking
  As a reader of the Egregora blog
  I want code references to link to the version that existed when the message was sent
  So that I can understand the discussion in its original context

Scenario: Explicit SHA Linking
  Given a chat message says "I fixed it in src/main.py (commit abc1234)"
  When the post is generated
  Then "src/main.py" should be a link to "https://github.com/org/repo/blob/abc1234/src/main.py"

Scenario: Implicit Timestamp Linking
  Given a chat message says "Check src/main.py" sent at "2024-01-01T12:00:00Z"
  And the git history shows commit "def4567" was the HEAD at that time
  When the post is generated
  Then "src/main.py" should be a link to "https://github.com/org/repo/blob/def4567/src/main.py"

Scenario: File Not Found Handling
  Given a chat message mentions "src/ghost.py"
  And that file did not exist in the repo at that time
  When the post is generated
  Then the text "src/ghost.py" should remain plain text (no broken link)
```

## 5. Implementation Plan (30 Days)

- [ ] **Day 1-5**: Implement `CodeReferenceDetector` (Regex + Abstract Syntax Tree for precision).
- [ ] **Day 6-15**: Implement `GitHistoryResolver`. Integrate with local `git` CLI to find commits by date.
- [ ] **Day 16-20**: Update `EnricherAgent` to use the resolver and inject Markdown links.
- [ ] **Day 21-25**: Add caching (Git lookups can be slow) to `DuckDB` or `pickle` cache.
- [ ] **Day 26-30**: Write tests and verify on a real repo history.

## 6. Success Metrics

- **Link Density**: % of file paths in chat that are successfully converted to links. Target > 80%.
- **Link Validity**: % of generated links that do not return 404. Target > 99%.
- **User Feedback**: (Qualitative) "This helped me understand why we wrote this code."

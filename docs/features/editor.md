# AI Editor Agent

The Editor Agent is an LLM-powered tool that can autonomously review and improve blog posts.

## Overview

After generating posts with the main pipeline, you can invoke the Editor Agent to:
- **Review** post quality and clarity
- **Suggest improvements** based on RAG context
- **Edit** posts line-by-line or rewrite entirely
- **Decide** whether to publish or hold for review

The Editor Agent has access to:
- ✅ **The post** (line-by-line editing interface)
- ✅ **RAG system** (search past posts for context)
- ✅ **Meta-LLM** (consult a separate LLM for ideas)
- ✅ **Editing tools** (line edits, full rewrites, finish)

## How It Works

### 1. Load Post

The Editor Agent receives a **DocumentSnapshot**:
```python
snapshot = DocumentSnapshot(
    doc_id="2025-01-15-ai-ethics",
    version=0,
    meta={"path": "posts/2025-01-15-ai-ethics.md"},
    lines={
        0: "---",
        1: "title: AI Ethics Discussion",
        2: "date: 2025-01-15",
        ...
    }
)
```

Each line is indexed for precise editing.

### 2. Review & Research

The Editor Agent can:
- **Query RAG** for related past posts
- **Ask Meta-LLM** for creative suggestions
- **Analyze** the content for clarity, accuracy, style

Example RAG query:
```python
# Editor Agent calls:
query_rag(query="AI alignment discussions", max_results=5)

# Returns:
[
    {"post": "2024-12-20-alignment.md", "excerpt": "..."},
    {"post": "2024-11-15-coordination.md", "excerpt": "..."},
]
```

### 3. Make Edits

The Editor Agent can edit in two ways:

**Option A: Line-by-line edits**
```python
edit_line(
    expect_version=0,
    index=5,
    new="The group discussed AI alignment challenges and coordination failures."
)
```

**Option B: Full rewrite**
```python
full_rewrite(
    expect_version=0,
    content="---\ntitle: AI Ethics\n..."
)
```

### 4. Finish

When done, the Editor Agent calls:
```python
finish(
    expect_version=1,
    decision="publish",  # or "hold"
    notes="Improved clarity in section 2. Added reference to past alignment post."
)
```

The post is saved with the edits applied.

## Usage

### Edit a Single Post

```bash
egregora edit posts/2025-01-15-ai-ethics.md \
  --gemini_key=YOUR_KEY \
  --rag_dir=./rag
```

This will:
1. Load the post into a DocumentSnapshot
2. Run the Editor Agent with RAG access
3. Apply edits and save the result
4. Log decision (publish/hold) and notes

### Edit Multiple Posts

```bash
# Edit all posts from a specific date
for post in posts/2025-01-*; do
    egregora edit "$post" --rag_dir=./rag
done
```

### Batch Editing

```python
from pathlib import Path
from egregora.editor_agent import run_editor_session
from google import genai

client = genai.Client(api_key="...")
rag_dir = Path("./rag")

for post_path in Path("posts").glob("2025-01-*.md"):
    result = await run_editor_session(
        post_path=post_path,
        client=client,
        rag_dir=rag_dir,
    )

    print(f"Post: {post_path.name}")
    print(f"Decision: {result.decision}")
    print(f"Notes: {result.notes}")
    print(f"Edits made: {result.edits_made}")
```

## Available Tools

### 1. edit_line

Replace a single line.

**Parameters:**
- `expect_version` (int) - Expected document version (for concurrency control)
- `index` (int) - Line index (0-based)
- `new` (str) - New content for this line

**Returns:**
```json
{"ok": true, "new_version": 1}
```

**Example:**
```python
# Fix a typo in line 10
edit_line(expect_version=0, index=10, new="The discussion focused on alignment.")
```

### 2. full_rewrite

Replace the entire document.

**Parameters:**
- `expect_version` (int) - Expected document version
- `content` (str) - New complete document content

**Returns:**
```json
{"ok": true, "new_version": 1, "line_count": 50}
```

**Example:**
```python
# Complete rewrite
full_rewrite(
    expect_version=0,
    content="""---
title: AI Alignment
date: 2025-01-15
---

# AI Alignment Challenges

[Improved content...]
"""
)
```

### 3. query_rag

Search past posts for relevant context.

**Parameters:**
- `query` (str) - Search query
- `max_results` (int, optional) - Maximum results (default: 5)

**Returns:**
```json
{
  "ok": true,
  "results": [
    {
      "post_path": "2024-12-20-alignment.md",
      "similarity": 0.85,
      "excerpt": "Previous discussion about AI alignment..."
    }
  ]
}
```

**Example:**
```python
# Find related posts
query_rag(query="coordination failures in AI safety", max_results=3)
```

### 4. ask_llm

Consult a separate LLM for ideas.

**Parameters:**
- `question` (str) - Question or request for the meta-LLM

**Returns:**
```json
{
  "ok": true,
  "response": "Here are three ways to improve this section..."
}
```

**Example:**
```python
# Get creative suggestions
ask_llm(question="How can I make the introduction more engaging?")
```

### 5. finish

Mark the document as ready to publish or hold.

**Parameters:**
- `expect_version` (int) - Expected document version
- `decision` (str) - "publish" or "hold"
- `notes` (str) - Editorial notes about changes made

**Returns:**
```json
{"ok": true, "decision": "publish"}
```

**Example:**
```python
finish(
    expect_version=3,
    decision="publish",
    notes="Fixed typos, improved clarity, added context from past posts."
)
```

## Editing Protocol

### Version Control

Each edit increments the document version:

```
Initial: version=0
edit_line() → version=1
edit_line() → version=2
full_rewrite() → version=3
finish() → done
```

**Optimistic concurrency:** Each tool call must provide `expect_version`. If it doesn't match the current version, the edit is rejected.

**Why?** This prevents race conditions if multiple editors work on the same document.

### Line Indexing

Lines are 0-indexed:

```
Line 0: ---
Line 1: title: AI Ethics
Line 2: date: 2025-01-15
Line 3: ---
Line 4:
Line 5: # AI Ethics Discussion
```

To edit line 5:
```python
edit_line(expect_version=0, index=5, new="# The AI Alignment Challenge")
```

## Configuration

### Custom Editor Prompt

Override the default editor prompt:

```python
from egregora.prompt_templates import render_editor_prompt

custom_prompt = render_editor_prompt(
    post_content="...",
    custom_instructions="Focus on technical accuracy and clarity."
)

# Use in run_editor_session()
```

### RAG Integration

The Editor Agent uses the same RAG system as the main pipeline:

```python
from egregora.rag import VectorStore

# Manages both chunks.parquet and chunks.duckdb
store = VectorStore(Path("./rag/chunks.parquet"))

# Editor Agent will query this store
```

See [RAG documentation](rag.md) for details.

## Use Cases

### 1. Post-Processing Pipeline

Generate posts, then automatically edit them:

```bash
# Generate
egregora process --zip_file=export.zip --output=./blog

# Edit all new posts
for post in blog/posts/2025-01-*; do
    egregora edit "$post" --rag_dir=./blog/rag
done
```

### 2. Quality Improvement

Review posts for quality issues:

```python
result = await run_editor_session(post_path, client, rag_dir)

if result.decision == "hold":
    print(f"⚠️  Post held: {result.notes}")
else:
    print(f"✅ Published: {result.notes}")
```

### 3. Consistency Enforcement

Use RAG to ensure consistent terminology:

```python
# Editor Agent queries RAG:
query_rag(query="How do we refer to 'LLM agents'?")

# Uses past posts to adopt consistent naming
```

### 4. Interactive Editing

Run the editor in a loop for human-in-the-loop editing:

```python
while True:
    result = await run_editor_session(post_path, client, rag_dir)

    print(f"Decision: {result.decision}")
    print(f"Notes: {result.notes}")

    if input("Accept changes? (y/n): ") == "y":
        break
```

## Performance

### Speed

- **Load post:** <0.1s
- **LLM calls:** ~1-3s each (depends on edits)
- **RAG queries:** ~0.5s each
- **Save:** <0.1s

**Total:** ~5-20 seconds per post (varies with complexity)

### Cost

Using Gemini 2.5 Flash:
- **Input:** ~$0.0001 per post (reading)
- **Output:** ~$0.0005 per post (edits)
- **RAG queries:** ~$0.0001 each

**Approximate cost:** $0.001-0.01 per post edited.

## Limitations

### 1. No Multi-Document Edits

The Editor Agent works on one post at a time.

**Workaround:** Run in a loop for batch editing.

### 2. No Undo/Redo

Once an edit is made, it's applied immediately.

**Mitigation:** Use git for version control:
```bash
git add posts/
git commit -m "Before editing"
# Run editor
git diff  # Review changes
```

### 3. RAG Quality Dependency

Editor quality depends on RAG index quality.

**Solution:** Ensure high-quality posts in your RAG index.

## Troubleshooting

### Version Mismatch Errors

**Problem:** `version_mismatch` when calling tools

**Solution:** Always use the latest version returned by previous tool calls:
```python
# After edit_line returns {"new_version": 1}
# Use expect_version=1 for next call
```

### No RAG Results

**Problem:** `query_rag` returns empty results

**Solution:**
1. Check RAG index exists: `ls -la rag/chunks.parquet rag/chunks.duckdb`
2. Ensure posts are indexed
3. Try broader queries

### Editor Agent Doesn't Edit

**Problem:** Editor calls `finish` without making changes

**Solution:**
- Check the prompt (may need more specific instructions)
- Enable debug mode to see LLM reasoning
- Try different custom instructions

## Future Enhancements

### Planned Features

1. **Multi-post editing** - Edit related posts together
2. **Diff preview** - Show changes before applying
3. **Undo/redo** - Revert specific edits
4. **Automated workflows** - E.g., "Fix all typos in posts from January"
5. **Quality scoring** - Numerical quality assessment

### Experimental Features

- **Style transfer** - Adapt posts to different writing styles
- **Translation** - Translate posts to other languages
- **Summarization** - Generate summaries for long posts
- **Fact-checking** - Verify claims against RAG knowledge base

## Related Documentation

- [RAG System](rag.md) - How RAG queries work
- [Architecture](../guides/architecture.md) - Where the editor fits
- [Post Ranking](ranking.md) - Quality assessment system *(optional extra)*

## Code Reference

**Source:** `src/egregora/editor_agent.py` and `src/egregora/editor.py`

**Key functions:**
- `run_editor_session()` - Main entry point
- `Editor.edit_line()` - Line-level editing
- `Editor.full_rewrite()` - Complete rewrite
- `Editor.finish()` - Mark as done

**Documented in code:** See inline comments in source files

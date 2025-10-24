# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
```bash
pip install egregora
pip install '.[docs,lint]'  # Install optional dependencies
```

### Testing
```bash
# Run all tests
pytest tests/

# Lint code
ruff check src/
black --check src/
```

### Key Project Configurations
- Python 3.11+ required
- Linting: ruff, black
- Type checking: mypy
- Line length: 100 characters
- Main CLI entry point: `egregora.cli:main`

## Architecture Overview

### Key Design Principles
- Ultra-simple pipeline
- LLM-driven content generation
- Privacy-first approach
- DataFrame-based processing

### Main Pipeline Components
- `parser.py`: Convert WhatsApp export to DataFrame
- `anonymizer.py`: Privacy transformations
- `enricher.py`: Add context to messages
- `write_post.py`: Generate blog posts
- `pipeline.py`: Orchestrate entire process

### Workflow
1. Parse WhatsApp export
2. Anonymize messages
3. Group by period
4. Optional enrichment
5. LLM generates posts

## Working with Jules API

### Delegation Strategy

**IMPORTANT**: Prefer delegating tasks to Jules whenever possible to maximize Claude's availability for higher-level work.

### When to Use Jules vs Claude

**Use Jules for:**
- ✅ Code reviews and refactoring
- ✅ Implementing well-defined features
- ✅ Bug fixes with clear reproduction steps
- ✅ Adding tests for existing code
- ✅ Documentation improvements
- ✅ Dependency updates
- ✅ Iterative improvements to existing PRs
- ✅ Any task that can run asynchronously

**Use Claude for:**
- 🎯 Initial design and architecture decisions
- 🎯 Complex problem-solving requiring context
- 🎯 Interactive debugging sessions
- 🎯 Learning and explaining codebase
- 🎯 Quick fixes that need immediate feedback
- 🎯 Tasks requiring multiple tool integrations

### How to Delegate to Jules

The Jules API skill (`.claude/skills/jules-api/`) enables easy delegation:

**Quick delegation pattern:**
```python
# 1. Push your branch
git push origin feature/my-branch

# 2. Create Jules session
source /home/user/workspace/.envrc
uvx --from requests python .claude/skills/jules-api/jules_client.py create \
  "Review and improve the code in feature/my-branch. Add tests and improve error handling." \
  franklinbaldo egregora feature/my-branch

# 3. Continue other work while Jules works asynchronously
# ⏱️  Jules typically completes tasks in ~10 minutes

# 4. Check back after ~10 minutes
python .claude/skills/jules-api/jules_client.py get <session-id>
```

**Or simply ask Claude:**
- "Create a Jules session to review this branch"
- "Ask Jules to add tests for this feature"
- "Delegate the refactoring to Jules"

### Best Practices for Jules Delegation

1. **Clear, specific prompts** - "Add unit tests for authentication" beats "improve tests"
2. **One branch per task** - Keep Jules sessions focused
3. **Review Jules' PRs** - Jules will create PRs for review, not auto-merge
4. **Iterate with feedback** - Use `sendMessage` to guide Jules if needed
5. **Use AUTO_CREATE_PR mode** - Let Jules create PRs automatically
6. **Document context** - Add relevant context in commit messages

### Typical Workflow

```
Claude creates initial implementation
    ↓
Push to feature branch
    ↓
Delegate to Jules for:
  - Code review
  - Adding tests
  - Refactoring
  - Documentation
    ↓
Jules creates PR with improvements
    ↓
Claude reviews Jules' changes
    ↓
Merge when ready
```

### Jules Session Management

```bash
# List all sessions
python .claude/skills/jules-api/jules_client.py list

# Check specific session
python .claude/skills/jules-api/jules_client.py get <session-id>

# Send feedback to active session
python .claude/skills/jules-api/jules_client.py message <session-id> \
  "Please also add integration tests"

# Get session activities (detailed progress)
python .claude/skills/jules-api/jules_client.py activities <session-id>
```

### Success Pattern from This Repository

1. Claude created GitHub Actions workflow + Jules API skill
2. Pushed to `feature/claude-code-integrations`
3. Created Jules session for code review
4. Jules found P1 auth bug and suggested improvements
5. Claude fixed the bug
6. Created new Jules session to verify the fix
7. Jules validated and enhanced the implementation

**Result**: Better code quality + saved Claude time for strategic work
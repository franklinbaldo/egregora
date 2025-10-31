# Documentation Templates

This directory contains Jinja2 templates for auto-generating project documentation.

## Purpose

To prevent documentation drift and inconsistencies, certain documentation files are generated from templates rather than manually edited. This ensures:

- **Consistency**: All agent-specific guides (CLAUDE.md, AGENTS.md, GEMINI.md) stay synchronized
- **Single source of truth**: Update one template, generate all variants
- **No drift**: Changes propagate to all generated files automatically

## Generated Files

The following files are auto-generated from templates:

- `CLAUDE.md` - Guide for Claude Code
- `AGENTS.md` - Guide for generic AI agents
- `GEMINI.md` - Guide for Gemini

All generated files include a warning header:
```markdown
<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY!
This file is generated from scripts/templates/AGENT_GUIDE.md.jinja2
To update this documentation, edit the template and run: python scripts/generate_docs.py
-->
```

## How to Update Documentation

### For Auto-Generated Files

1. **Edit the template** in `scripts/templates/` (e.g., `AGENT_GUIDE.md.jinja2`)
2. **Run the generator**:
   ```bash
   python scripts/generate_docs.py
   ```
3. **Commit both** the template and generated files

### For Manual Files

Files not listed above can be edited directly:
- `README.md`
- `CONTRIBUTING.md`
- Design documents (`*_DESIGN.md`)
- Setup guides (`.github/AUTO_REVIEW_SETUP.md`)

## Templates

### AGENT_GUIDE.md.jinja2

Template for agent-specific documentation guides.

**Variables:**
- `agent_name`: Uppercase name (e.g., "CLAUDE", "AGENTS", "GEMINI")
- `agent_display_name`: Human-readable name (e.g., "Claude Code", "the Agent", "Gemini")

**Generates:**
- Development commands and setup instructions
- Architecture overview
- Jules API delegation strategies
- Best practices

## CI Integration

A CI check validates that all auto-generated documentation is up-to-date:

```bash
# Generate docs and check for changes
python scripts/generate_docs.py
git diff --exit-code CLAUDE.md AGENTS.md GEMINI.md
```

If this check fails, run `python scripts/generate_docs.py` and commit the changes.

## Adding New Templated Documentation

To add a new auto-generated documentation file:

1. Create a new template in `scripts/templates/`
2. Add generation logic to `scripts/generate_docs.py`
3. Add the output files to the CI check
4. Document it in this README

## Why Not Use Symlinks or Includes?

We generate separate files instead of using symlinks or Markdown includes because:

- **Agent-specific customization**: Some sections need agent-specific wording
- **GitHub rendering**: Generated files render correctly in GitHub UI
- **Offline reading**: No build step needed to read documentation
- **Search indexing**: Each file is independently searchable
- **Clarity**: Explicit files are easier to understand than indirection

The trade-off is that we must remember to regenerate after template changes, which the CI check enforces.

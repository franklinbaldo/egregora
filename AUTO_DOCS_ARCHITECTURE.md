# Automatic Documentation Architecture

## Overview

This document describes Egregora's 100% automatic documentation system. **No manual API documentation is needed** - everything is generated from code.

## Two-Tier Auto-Documentation

### 1. Project-Level Documentation (Agent Guides)

**Purpose**: Keep agent-specific guides (CLAUDE.md, AGENTS.md, GEMINI.md) synchronized

**Implementation**:
- **Template**: `scripts/templates/AGENT_GUIDE.md.jinja2`
- **Generator**: `scripts/generate_docs.py`
- **CI Check**: `.github/workflows/check-docs.yml`

**Usage**:
```bash
# Edit template
vim scripts/templates/AGENT_GUIDE.md.jinja2

# Generate all variants
python scripts/generate_docs.py

# Commit both template and generated files
git add scripts/templates/ CLAUDE.md AGENTS.md GEMINI.md
git commit -m "docs: update agent guides"
```

**Generated Files**:
- `CLAUDE.md` - Guide for Claude Code
- `AGENTS.md` - Guide for generic AI agents
- `GEMINI.md` - Guide for Gemini

All include warning headers to prevent manual editing.

### 2. API Reference Documentation (MkDocs + mkdocstrings)

**Purpose**: Auto-generate complete API documentation from Python docstrings

**Implementation**:
- **Plugin**: mkdocstrings with Python handler
- **Style**: Google-style docstrings
- **Scaffolding**: `src/egregora/publication/site/scaffolding.py`
- **Templates**: `src/egregora/publication/site/templates/`

**How It Works**:

1. **User runs `egregora init`** (creates a new MkDocs site)
2. **Scaffolding auto-generates**:
   - `mkdocs.yml` with mkdocstrings configured
   - `docs/api/` directory structure
   - API reference pages for all modules
3. **mkdocstrings extracts** docstrings from source code at build time
4. **Zero manual maintenance** - docs always match code

**Generated Structure**:
```
docs/
├── index.md (homepage)
├── about.md
├── posts/ (blog)
├── profiles/ (participants)
└── api/ (100% AUTO-GENERATED)
    ├── index.md (API overview)
    ├── core/
    │   └── database_schema.md → ::: egregora.core.database_schema
    ├── ingestion/
    │   └── parser.md → ::: egregora.ingestion.parser
    ├── privacy/
    │   ├── anonymizer.md → ::: egregora.privacy.anonymizer
    │   └── detector.md → ::: egregora.privacy.detector
    ├── augmentation/
    ├── generation/
    ├── knowledge/
    ├── publication/
    ├── orchestration/
    └── utils/
```

**API Page Template**:
```markdown
# Module Title

::: module.path.here
```

The `:::` syntax tells mkdocstrings to extract and render documentation from that module's docstrings.

## Configuration

### pyproject.toml
```toml
[project.optional-dependencies]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.24.0",  # ← Key dependency
    ...
]
```

### mkdocs.yml (generated)
```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: true
            members_order: source
            filters: ["!^_"]  # Hide private members
```

## Docstring Standards

All public APIs must use Google-style docstrings:

```python
def my_function(arg: str, flag: bool = False) -> dict[str, Any]:
    """One-line summary of what the function does.

    Longer description if needed. Explain edge cases, behavior,
    and important details.

    Args:
        arg: Description of the argument
        flag: Description of the flag (default: False)

    Returns:
        Dictionary containing results with keys:
            - "status": Success status
            - "data": Result data

    Raises:
        ValueError: If arg is empty
        FileNotFoundError: If required file missing

    Example:
        >>> result = my_function("test", flag=True)
        >>> result["status"]
        "success"
    """
    ...
```

## Benefits

### For Project Docs (Agent Guides)

✅ **No drift** - Single template, multiple outputs
✅ **CI enforced** - Can't commit out-of-sync docs
✅ **Easy updates** - Change once, propagate everywhere
✅ **Clear ownership** - Template is source of truth

### For API Docs (mkdocstrings)

✅ **Always current** - Extracted from code at build time
✅ **Zero maintenance** - No manual sync needed
✅ **Search works** - MkDocs indexes everything
✅ **Type hints shown** - Full signature display
✅ **Source links** - Jump to implementation
✅ **No duplication** - Docstrings are the docs

## Anti-Patterns (What We Avoid)

❌ **Manual API docs** - Would drift from code
❌ **Copy-paste docs** - Would diverge over time
❌ **Separate doc repos** - Would lag behind code
❌ **Wiki pages** - Would become stale
❌ **Markdown API tables** - Manual and brittle

## Workflow

### For Code Changes

1. **Write code** with Google-style docstrings
2. **Commit** - API docs update automatically
3. **Done** - No manual doc updates needed

### For Agent Guide Changes

1. **Edit template** - `scripts/templates/AGENT_GUIDE.md.jinja2`
2. **Generate** - `python scripts/generate_docs.py`
3. **Commit** - Template + generated files
4. **CI validates** - Ensures docs are in sync

### For API Structure Changes

If you add/remove/rename modules:

1. **Update `scaffolding.py`** - Add/remove from `api_modules` list
2. **Test** - Run `egregora init` in test directory
3. **Commit** - Scaffolding change only

The next `egregora init` will generate the new structure.

## Testing

### Test Project Docs Generation

```bash
python scripts/generate_docs.py
git diff CLAUDE.md AGENTS.md GEMINI.md
```

### Test API Docs Generation

```bash
# Create test site
mkdir /tmp/test_site
cd /tmp/test_site
egregora init

# Build docs
mkdocs build

# Serve docs
mkdocs serve
# Open http://localhost:8000/api/
```

### Test CI Check

```bash
# Should pass if docs are up-to-date
python scripts/generate_docs.py
git diff --exit-code CLAUDE.md AGENTS.md GEMINI.md
```

## Future Enhancements

### Possible additions:

- **Auto-generate CLI docs** - Extract from Typer decorators
- **Tutorial generation** - From example scripts
- **Changelog automation** - From conventional commits
- **Diagram generation** - From code structure
- **Performance docs** - From benchmark results

### Guiding principle:

> **If it can be generated from code, it should be**

Only write documentation that adds information not already in the code (architecture decisions, design rationale, tutorials).

## Maintenance

### Quarterly Review

- [ ] Check if new modules need API docs
- [ ] Verify docstring coverage for public APIs
- [ ] Review mkdocstrings configuration for new features
- [ ] Update templates if agent guide structure changes

### When Refactoring

- [ ] Update module paths in `scaffolding.py` if moved
- [ ] Ensure docstrings move with code
- [ ] No manual doc updates needed

## References

- [mkdocstrings documentation](https://mkdocstrings.github.io/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)

---

**TL;DR**: Write docstrings. Run generators. Everything else is automatic.

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
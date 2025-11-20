# Testing Documentation

This directory contains documentation for Egregora's testing strategy and practices.

## Documents

### [E2E Testing Strategy](e2e_strategy.md)

Comprehensive guide to End-to-End testing in Egregora, including:

- **Philosophy**: Core principles for E2E testing (Real I/O, Mocked Intelligence)
- **Current State**: Assessment of existing test infrastructure
- **Gap Analysis**: Coverage gaps and technical debt
- **Target Architecture**: Three-layer E2E test structure (Input → Pipeline → Output)
- **Refactoring Plan**: 6-phase plan to modernize test suite
- **Implementation Guidelines**: Patterns and best practices for writing new tests

**Status**: Draft - Ready for Review (2025-11-19)

## Quick Reference

### Test Directory Structure (Target)

```
tests/
├── e2e/
│   ├── input_adapters/    # WhatsApp, Slack parsing → IR
│   ├── pipeline/          # Full orchestration with mocked agents
│   ├── output_adapters/   # MkDocs, Eleventy serialization
│   └── cli/               # CLI command integration
├── integration/           # Infrastructure (RAG, DuckDB, enrichment)
├── unit/                  # Pure functions
└── helpers/               # Test utilities and mocks
```

### Mocking Quick Reference

| Test Type | Mock Strategy |
|-----------|---------------|
| Unit | `unittest.mock.patch` for external deps |
| Integration | Live API calls (GOOGLE_API_KEY) or mocks |
| E2E Input | No mocking (real files) |
| E2E Pipeline | `pydantic_ai.models.test.TestModel` for agents |
| E2E Output | No mocking (real file writes) |

### Running Tests

```bash
# All tests
uv run pytest tests/

# E2E only
uv run pytest tests/e2e/

# Specific layer
uv run pytest tests/e2e/input_adapters/
uv run pytest tests/e2e/pipeline/
uv run pytest tests/e2e/output_adapters/

# With coverage
uv run pytest --cov=egregora tests/
```

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Development guidelines and recent changes
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
- [Architecture Docs](../architecture/) - System architecture documentation

## Contributing

When adding new testing documentation:

1. Follow the existing structure (Philosophy → Current → Plan → Implementation)
2. Include code examples for patterns and best practices
3. Update this README with links to new documents
4. Keep examples practical and based on real codebase code

## Questions?

- Review existing test files in `tests/` for examples
- Check `tests/helpers/` for reusable test utilities
- See `e2e_strategy.md` for comprehensive guidance

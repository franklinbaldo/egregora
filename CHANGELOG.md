# Changelog

All notable changes to Egregora will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No unreleased changes._

## [2.0.0] - 2024-05-20

### Added
- Comprehensive documentation structure in `docs/` directory
  - Getting started guides (installation, quickstart, concepts)
  - Feature documentation (anonymization, privacy commands, ranking, RAG, editor)
  - Guides (architecture, configuration, troubleshooting)
  - Reference (CLI, API)
  - Contributing guides
- ELO-based ranking system for post quality assessment
- AI Editor Agent for autonomous post improvement
- RAG (Retrieval-Augmented Generation) system for context-aware posts
- Multi-post generation per day with automatic thread detection
- User privacy commands (`/egregora` prefix for opt-out, aliases, etc.)
- DuckDB-based storage for RAG vectors and ranking data
- Profile impersonation in ranking for diverse perspectives
- Code comments linking to documentation (anti-drift measure)

### Changed
- Simplified architecture from agent-based to functional pipeline (~80% code reduction)
- Moved from complex agent system to simple LLM-with-tools approach
- Trust-the-LLM philosophy: Let LLM make editorial decisions
- Documentation reorganized from root-level files to structured `docs/` directory
- Updated README with comprehensive navigation to new docs

### Removed
- CuratorAgent (LLM filters automatically)
- EnricherAgent (replaced with simple function)
- WriterAgent (replaced with simple function)
- ProfilerAgent (replaced with simple function)
- Message/Topic/Post classes (work with DataFrames directly)
- Tool registry system (over-engineered)
- Agent base classes and abstractions
- Event sourcing system (unnecessary complexity)

### Deprecated
- Old documentation files (QUICKSTART_V2.md, ARCHITECTURE_V2.md, REFACTORING_PLAN.md)
  - Will be removed in next release
  - Replaced by new `docs/` structure

### Fixed
- Timezone handling in WhatsApp export parsing
- Lazy imports and magic values for ruff compliance
- Privacy validation edge cases

## [0.1.0] - Initial Release

### Added
- Basic WhatsApp export parsing
- UUID5-based anonymization
- LLM-powered blog post generation
- MkDocs site scaffolding
- Basic CLI commands (init, process)
- Privacy-first approach

---

## Release Guidelines

### Version Numbers

- **MAJOR** (X.0.0): Breaking changes to API or CLI
- **MINOR** (0.X.0): New features, backwards compatible
- **PATCH** (0.0.X): Bug fixes, backwards compatible

### What Goes in Changelog

- All user-facing changes
- Breaking changes (with migration guide)
- New features and improvements
- Important bug fixes
- Deprecations and removals

### What Doesn't Go in Changelog

- Internal refactorings (unless they affect users)
- Documentation typo fixes
- Test improvements
- CI/CD changes

## Links

- [Unreleased Changes](https://github.com/franklinbaldo/egregora/compare/v0.1.0...HEAD)
- [Full Changelog](https://github.com/franklinbaldo/egregora/blob/main/CHANGELOG.md)
- [GitHub Releases](https://github.com/franklinbaldo/egregora/releases)

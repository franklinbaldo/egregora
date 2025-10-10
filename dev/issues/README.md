# Egregora Development Issues

This directory contains detailed issue documentation for Egregora improvements based on real-world testing and analysis.

## GitHub Synchronization

All files in this folder are automatically synchronized with GitHub Issues. A
GitHub Actions workflow runs hourly, on every change to `dev/issues`, and in
response to issue updates on GitHub to keep both sides aligned. Each Markdown
file contains a short HTML comment block at the top where the synchronization
metadata (linked GitHub issue number, state, last sync timestamp, and a content
hash) is stored—please leave this block intact.

To sync manually you can run `python scripts/issue_sync.py` locally (provide
`GITHUB_TOKEN`/`GITHUB_REPOSITORY` if not running inside GitHub Actions). Any
edits to the Markdown body will be reflected in the matching GitHub issue, and
updates performed directly on GitHub will be mirrored back into the
corresponding Markdown file.

## Issue Categories

### 🚨 High Priority Issues

- **[#001: Offline/Demo Mode](001-offline-demo-mode.md)** - Enable testing without API key
- **[#002: Configuration UX](002-configuration-ux.md)** - Improve setup and configuration experience  
- **[#003: Error Messages & Debugging](003-error-messages-debugging.md)** - Better error handling and user feedback
- **[#009: Privacy & Security Enhancement](009-privacy-security.md)** - Enhanced privacy controls and audit

### 🔧 Medium Priority Issues

- **[#004: Dependency Management](004-dependency-management.md)** - Update deprecated dependencies and improve AI provider handling
- **[#005: Performance & Scalability](005-performance-scalability.md)** - Progress indicators, streaming, and parallel processing
- **[#006: Testing & Development](006-testing-development.md)** - Improved test infrastructure and development experience
- **[#007: Media Handling](007-media-handling.md)** - Enhanced media processing with thumbnails and optimization

### 🎨 Low Priority Issues

- **[#008: Output Formats](008-output-formats.md)** - Multiple output formats (HTML, PDF, RSS, JSON)

## Quick Wins (High Impact, Low Effort)

1. **Filter deprecation warnings** from end-user output (#003, #004)
2. **Add `--check-config` command** to validate configuration (#002)
3. **Create specific error for missing API key** with helpful message (#003)
4. **Add progress indicators** for long-running operations (#005)
5. **Update core dependencies** to latest stable versions (#004)

## Testing Results Summary

Based on testing with a real 208MB WhatsApp export:

### ✅ What Works Well
- Core parsing and anonymization (7 senders, 132 lines processed)
- Group discovery and date range detection
- Polars-based data processing pipeline
- Test suite (15/15 tests passing)
- CLI commands (`--dry-run`, `--list`, `discover`)

### ❌ What Needs Improvement
- Requires valid Gemini API key for basic functionality
- 25+ deprecation warnings in output
- Complex configuration with poor validation
- No progress indicators for large files
- Limited error messages with long stack traces

## Implementation Strategy

### Phase 1: Foundation (Weeks 1-2)
- Implement demo mode (#001)
- Improve error messages (#003)
- Update dependencies (#004)

### Phase 2: User Experience (Weeks 3-4)
- Configuration wizard (#002)
- Performance improvements (#005)
- Testing infrastructure (#006)

### Phase 3: Advanced Features (Weeks 5-8)
- Media enhancements (#007)
- Output formats (#008)
- Privacy features (#009)

## Contributing

When working on these issues:

1. **Follow the acceptance criteria** listed in each issue
2. **Update tests** to cover new functionality
3. **Update documentation** for user-facing changes
4. **Consider backwards compatibility** for configuration changes
5. **Test with real WhatsApp exports** to ensure functionality

## Priority Matrix

| Issue | Impact | Effort | Priority | Notes |
|-------|--------|--------|----------|-------|
| #001 | High | Medium | 🚨 | Blocks new user adoption |
| #002 | High | Medium | 🚨 | Major UX improvement |
| #003 | High | Low | 🚨 | Quick wins available |
| #009 | High | Medium | 🚨 | Important for trust |
| #004 | Medium | Low | 🔧 | Technical debt |
| #005 | Medium | Medium | 🔧 | Scalability concerns |
| #006 | Medium | Medium | 🔧 | Developer experience |
| #007 | Medium | Medium | 🔧 | Feature enhancement |
| #008 | Low | Medium | 🎨 | Nice to have |

## Architecture Considerations

### Plugin System
Several issues (#004, #008) suggest need for a plugin architecture:
- Pluggable AI providers
- Custom output formatters
- Extensible anonymization strategies

### API-First Approach
Issues #008 and #011 suggest REST API benefits:
- Better separation of concerns
- Easier testing and integration
- Web interface built on API

### Configuration Management
Issues #002 and #009 highlight configuration complexity:
- Hierarchical configuration (basic → advanced)
- Environment-specific overrides
- Validation and migration tools

## Related Documentation

- [Architecture Overview](../docs/architecture.md)
- [Development Guide](../docs/development.md)
- [Testing Strategy](../docs/testing.md)
- [Privacy Implementation](../docs/privacy.md)
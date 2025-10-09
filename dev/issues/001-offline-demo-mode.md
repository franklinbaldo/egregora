# Issue #001: Offline/Demo Mode for Testing Without API Key

## Priority: High
## Effort: Medium
## Type: Enhancement

## Problem Description

Currently, Egregora completely fails when no valid Gemini API key is provided, even for basic functionality like parsing and anonymization. This creates barriers for:

- New users wanting to test the system
- Development and debugging
- CI/CD environments
- Users who want to evaluate before committing to API costs

**Error observed:**
```
ClientError: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.'}}
```

## Current Behavior

1. User runs `uv run egregora --disable-enrichment`
2. Pipeline successfully parses WhatsApp data and performs anonymization 
3. System crashes when attempting post generation (requires AI)
4. No output is produced despite successful parsing

## Proposed Solution

### Add `--demo-mode` Flag

```bash
# Enable demo mode for testing without API
uv run egregora --demo-mode --days 1

# Should work with existing flags
uv run egregora --demo-mode --dry-run --list
```

### Demo Mode Features

1. **Mock Post Generation**: Use templates instead of AI
   - Pre-written templates for different group types
   - Fill with anonymized content and metadata
   - Include sample enrichment data

2. **Sample Outputs**: Generate example posts showing:
   - Anonymization results
   - Media extraction
   - Transcript formatting
   - Profile generation (mock data)

3. **Progress Indicators**: Show what would happen with real API
   - "Would enrich 5 links (demo: skipped)"
   - "Would generate profile for Member-ABC1 (demo: using template)"

### Implementation Details

#### Configuration Changes
```toml
[demo]
enabled = false
template_dir = "templates/demo"
sample_enrichment = true
mock_profiles = true
```

#### Code Structure
```python
class DemoPostGenerator:
    """Generates mock posts without requiring AI API."""
    
    def generate_post(self, context: PostContext) -> str:
        template = self.load_template(context.group_type)
        return template.render(
            group_name=context.group_name,
            date=context.date,
            messages=context.anonymized_messages,
            mock_enrichment=self.generate_mock_enrichment()
        )
```

#### CLI Integration
```python
@click.option('--demo-mode', is_flag=True, 
              help='Run without API key using mock data')
def main(demo_mode: bool, ...):
    if demo_mode:
        processor = DemoProcessor(config)
    else:
        processor = UnifiedProcessor(config)
```

## Expected Benefits

1. **Improved Onboarding**: Users can try before committing to API costs
2. **Better Development**: Faster iteration without API calls
3. **Testing**: Reliable CI/CD without external dependencies
4. **Documentation**: Clear examples of expected outputs

## Acceptance Criteria

- [ ] `--demo-mode` flag works without any API key
- [ ] Generates realistic mock posts with anonymized data
- [ ] All existing functionality (parsing, anonymization, discovery) works
- [ ] Clear indicators that system is in demo mode
- [ ] Documentation with example workflows
- [ ] Demo templates for common group types

## Implementation Notes

### Phase 1: Basic Demo Mode
- Simple template-based post generation
- Mock enrichment data
- Basic progress indicators

### Phase 2: Enhanced Templates
- Multiple template styles
- Configurable mock data
- Integration with existing themes

### Phase 3: Interactive Demo
- Web interface for demo mode
- Sample data downloads
- Tutorial workflows

## Related Issues

- #002: Configuration UX Issues
- #003: Error Messages & Debugging
- #008: Output Formats

## Files to Modify

- `src/egregora/__main__.py` - Add CLI flag
- `src/egregora/config.py` - Demo configuration
- `src/egregora/processor.py` - Demo processor class
- `templates/demo/` - Template files
- `docs/` - Documentation updates
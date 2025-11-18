# Testing

Egregora uses a comprehensive testing strategy to ensure code quality and maintainability.

## Test Structure

Tests are organized by type and component:

```
tests/
├── unit/                 # Unit tests for individual functions/classes
│   ├── test_privacy/     # Privacy module tests
│   ├── test_enrichment/  # Enrichment module tests
│   └── test_agents/      # Agent module tests
├── integration/          # Integration tests for module interactions
├── e2e/                 # End-to-end tests for complete workflows
└── fixtures/            # Test data and configuration
```

## Running Tests

### All Tests

```bash
# Run the entire test suite
pytest

# Run with coverage
pytest --cov=egregora

# Run with verbose output
pytest -v
```

### Specific Tests

```bash
# Run unit tests only
pytest tests/unit/

# Run tests for a specific module
pytest tests/unit/test_privacy/

# Run a single test file
pytest tests/unit/test_privacy/test_anonymizer.py

# Run tests matching a pattern
pytest -k "anonymizer"
```

## Test Types

### Unit Tests

Test individual functions and classes in isolation:

```python
def test_anonymize_names():
    text = "Hi John, how are you?"
    result = anonymizer.anonymize_names(text)
    assert "ANON_PERSON_1" in result
    assert "John" not in result
```

### Integration Tests

Test how multiple modules work together:

```python
def test_complete_privacy_pipeline():
    # Test the complete flow from input to anonymized output
    input_data = load_test_data()
    anonymized = privacy_pipeline.process(input_data)
    assert no_pii_in_output(anonymized)
```

### End-to-End Tests

Test complete workflows:

```python
def test_whatsapp_to_mkdocs():
    # Test complete flow from WhatsApp input to MkDocs output
    result = run_complete_pipeline(
        input_path="tests/fixtures/whatsapp_sample.txt",
        output_format="mkdocs"
    )
    assert result.success
    assert output_contains_expected_content(result.output_dir)
```

## Test Fixtures

Egregora uses pytest fixtures for test setup:

### VCR Cassettes

For tests that make external API calls, we use VCR to record and replay HTTP interactions:

```python
import vcr

@vcr.use_cassette('tests/fixtures/cassettes/test_enrichment.yaml')
def test_topic_enrichment():
    # This test will use recorded API responses
    result = topic_enricher.enrich(sample_data)
    assert result.topics
```

### Sample Data

Test fixtures provide sample data for different scenarios:

- `tests/fixtures/whatsapp_sample.txt` - Sample WhatsApp export
- `tests/fixtures/slack_sample.json` - Sample Slack export
- `tests/fixtures/empty_conversation.txt` - Minimal conversation for edge case testing
- `tests/fixtures/edge_cases.json` - Conversations with special characters, etc.

## Mocking Strategy

To isolate units under test:

```python
from unittest.mock import Mock, patch

def test_writer_agent_with_mock_llm():
    mock_llm = Mock()
    mock_llm.generate.return_value = "Mocked response"
    
    agent = WriterAgent(llm=mock_llm)
    result = agent.generate_content(context_data)
    
    assert result == "Mocked response"
    mock_llm.generate.assert_called_once()
```

## Test Patterns

### Parametrized Tests

For testing multiple inputs:

```python
import pytest

@pytest.mark.parametrize("pii_type,should_detect", [
    ("John", True),
    ("john@example.com", True),
    ("123-456-7890", True),
    ("randomword", False),
])
def test_pii_detection_types(pii_type, should_detect):
    result = detector.detect_pii(pii_type)
    assert (len(result) > 0) == should_detect
```

### Property-Based Testing

For testing general properties across many inputs:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_anonymizer_preserves_length(text):
    original_length = len(text)
    anonymized = anonymizer.anonymize(text)
    # Anonymized text should be same or longer (not shorter)
    assert len(anonymized) >= original_length
```

## Continuous Integration

Tests run automatically on all pull requests and commits:

- Unit tests: Run on every push
- Integration tests: Run on every push  
- E2E tests: Run nightly or on release candidates
- Coverage: Must maintain or improve overall coverage

## Writing Good Tests

### Test Structure (AAA Pattern)

1. **Arrange**: Set up the test data and objects
2. **Act**: Execute the functionality being tested
3. **Assert**: Verify the expected outcomes

```python
def test_message_context_windowing():
    # Arrange
    messages = [Message(...), Message(...)]
    
    # Act
    result = windower.group_by_context(messages)
    
    # Assert
    assert len(result) > 0
    assert isinstance(result[0], ContextGroup)
```

### Test Coverage

Aim for high coverage of:

- Edge cases and error conditions
- Different input types and formats
- Configuration variations
- Performance characteristics

### Test Naming

Use descriptive names that explain what is being tested:

- `test_anonymizer_handles_unicode_characters`
- `test_writer_agent_fails_gracefully_on_empty_context`
- `test_rag_retrieval_returns_most_relevant_results`

## Testing Privacy

Special attention is given to privacy-related tests:

```python
def test_no_pii_leaks_to_external_services():
    # Verify that no actual PII is sent to external APIs
    with capture_network_traffic() as traffic:
        result = external_enrichment.process(anonymized_data)
        
    for request in traffic:
        assert_no_pii_in_request(request)
```
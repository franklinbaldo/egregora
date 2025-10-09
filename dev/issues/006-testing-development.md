# Issue #006: Testing & Development

## Priority: Medium
## Effort: Medium
## Type: Technical Debt

## Problem Description

While core tests exist and pass, the testing infrastructure could be improved for better development experience and confidence:

1. **Complex AI Mocking**: Tests need to mock complex AI interactions
2. **Limited Integration Tests**: Most tests are unit-level
3. **No Performance Tests**: No benchmarks for regression detection  
4. **Missing Test Data**: Limited variety in test WhatsApp exports
5. **Development Environment**: Could be more streamlined

**Current test status:**
- ✅ 8/8 core pipeline tests pass
- ✅ 3/3 WhatsApp integration tests pass  
- ✅ 4/4 anonymization tests pass
- ⚠️ 25+ deprecation warnings in test output
- ❌ No performance/load testing
- ❌ Limited test data variety

## Current Behavior

### Test Warnings
```bash
pytest tests/
======================== 15 passed, 30 warnings in 7.28s ========================
# Too many deprecation warnings obscure real issues
```

### Mock Complexity
```python
# Current AI mocking is complex and brittle
@patch('egregora.system_classifier.GeminiModel')
def test_classification(mock_model):
    mock_model.return_value.generate.return_value = MockResponse(...)
    # Complex setup for each test
```

### Limited Test Data
```
tests/data/
├── Conversa do WhatsApp com Teste.txt  # Single test file
└── zips/
    └── Conversa do WhatsApp com Teste.zip  # Single test zip
```

## Proposed Solution

### 1. Improved AI Mocking Infrastructure

```python
# tests/fixtures/ai_responses.py
class AIResponseFixtures:
    """Centralized AI response fixtures."""
    
    CLASSIFICATION_RESPONSES = {
        "system_message": '{"is_system": true, "confidence": 0.95}',
        "user_message": '{"is_system": false, "confidence": 0.98}',
        "unclear_message": '{"is_system": false, "confidence": 0.6}'
    }
    
    ENRICHMENT_RESPONSES = {
        "news_article": {
            "summary": "Tech news about AI development",
            "key_points": ["AI progress", "Industry impact"],
            "tone": "informative",
            "relevance": 4
        },
        "social_media": {
            "summary": "Social media post about daily life", 
            "key_points": ["Personal update"],
            "tone": "casual",
            "relevance": 2
        }
    }

# tests/conftest.py
@pytest.fixture
def mock_ai_provider():
    """Mock AI provider that returns realistic responses."""
    with patch('egregora.providers.GoogleAIProvider') as mock:
        provider = MockAIProvider(AIResponseFixtures())
        mock.return_value = provider
        yield provider

class MockAIProvider:
    def __init__(self, fixtures: AIResponseFixtures):
        self.fixtures = fixtures
        self.call_count = 0
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        
        # Route to appropriate response based on prompt content
        if "classify" in prompt.lower():
            return self.fixtures.get_classification_response(prompt)
        elif "enrich" in prompt.lower():
            return self.fixtures.get_enrichment_response(prompt)
        else:
            return "Mock response for: " + prompt[:50] + "..."
```

### 2. Test Data Generation

```python
# tests/generators/whatsapp_data.py
class WhatsAppTestDataGenerator:
    """Generate realistic test WhatsApp exports."""
    
    def generate_export(self, 
                       group_name: str,
                       num_participants: int = 5,
                       num_days: int = 7,
                       messages_per_day: int = 50,
                       include_media: bool = True,
                       include_links: bool = True) -> Path:
        """Generate a realistic WhatsApp export for testing."""
        
        participants = [f"Participant {i}" for i in range(num_participants)]
        export_dir = self.temp_dir / f"test_{group_name}"
        export_dir.mkdir(exist_ok=True)
        
        # Generate chat file
        chat_content = []
        for day in range(num_days):
            date = datetime.now() - timedelta(days=day)
            
            for msg_idx in range(messages_per_day):
                sender = random.choice(participants)
                time_str = self.random_time()
                content = self.generate_message_content(include_media, include_links)
                
                line = f"{date.strftime('%d/%m/%Y')}, {time_str} - {sender}: {content}"
                chat_content.append(line)
        
        # Write chat file
        chat_file = export_dir / f"{group_name}.txt"
        chat_file.write_text('\n'.join(chat_content), encoding='utf-8')
        
        # Create ZIP
        zip_path = export_dir.parent / f"{group_name}.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(chat_file, chat_file.name)
            
            # Add media files if requested
            if include_media:
                self.add_media_files(zf, export_dir)
        
        return zip_path
    
    def generate_message_content(self, include_media: bool, include_links: bool) -> str:
        """Generate realistic message content."""
        message_types = [
            "Hey everyone! How's your day going?",
            "Did you see the news about {topic}?",
            "Thanks for sharing that article earlier",
            "Looking forward to the meetup next week",
            "Just finished reading an interesting paper",
        ]
        
        content = random.choice(message_types)
        
        if include_links and random.random() < 0.1:  # 10% chance of link
            content += " " + self.random_link()
        
        if include_media and random.random() < 0.05:  # 5% chance of media
            return "<Media omitted>"
        
        return content.format(topic=random.choice(["AI", "climate", "tech", "science"]))

# Usage in tests
@pytest.fixture
def sample_export():
    generator = WhatsAppTestDataGenerator()
    return generator.generate_export(
        group_name="test_group",
        num_participants=3,
        num_days=2,
        messages_per_day=10
    )
```

### 3. Performance Testing Framework

```python
# tests/performance/test_benchmarks.py
import pytest
import time
import psutil
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    operation: str
    duration: float
    memory_mb: float
    items_processed: int
    
    @property
    def items_per_second(self) -> float:
        return self.items_processed / self.duration

class BenchmarkSuite:
    """Performance benchmarking for Egregora operations."""
    
    @pytest.mark.benchmark
    def test_parsing_performance(self, large_test_export):
        """Benchmark WhatsApp parsing performance."""
        with self.measure("parsing") as metrics:
            result = parse_whatsapp_export(large_test_export)
            metrics.items_processed = len(result.messages)
        
        # Performance assertions
        assert metrics.duration < 10.0  # Should parse in under 10s
        assert metrics.items_per_second > 100  # Should process >100 messages/s
        assert metrics.memory_mb < 500  # Should use <500MB memory
    
    @pytest.mark.benchmark  
    def test_anonymization_performance(self, sample_messages):
        """Benchmark anonymization performance."""
        anonymizer = Anonymizer(AnonymizationConfig())
        
        with self.measure("anonymization") as metrics:
            for message in sample_messages:
                anonymizer.anonymize_author(message.sender)
            metrics.items_processed = len(sample_messages)
        
        assert metrics.items_per_second > 1000  # Should be very fast
    
    @contextmanager
    def measure(self, operation: str):
        """Context manager for performance measurement."""
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024
        start_time = time.time()
        
        metrics = BenchmarkResult(operation, 0, 0, 0)
        yield metrics
        
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024
        
        metrics.duration = end_time - start_time
        metrics.memory_mb = end_memory - start_memory

# Run benchmarks
pytest tests/performance/ --benchmark-only
```

### 4. Integration Test Improvements

```python
# tests/integration/test_end_to_end.py
class TestEndToEndWorkflows:
    """Test complete workflows with realistic data."""
    
    def test_complete_pipeline_small_group(self, temp_config, sample_export):
        """Test complete pipeline with small realistic group."""
        config = temp_config
        config.enrichment.enabled = False  # Disable for speed
        
        processor = UnifiedProcessor(config)
        
        # Should complete without errors
        results = processor.process_groups([sample_export])
        
        # Verify outputs
        assert len(results) == 1
        assert results[0].posts_generated > 0
        assert results[0].participants_anonymized > 0
        
        # Check output files exist
        output_dir = config.posts_dir / sample_export.slug
        assert (output_dir / "posts" / "daily").exists()
    
    def test_error_recovery(self, temp_config, corrupted_export):
        """Test graceful handling of corrupted data."""
        processor = UnifiedProcessor(temp_config)
        
        # Should handle errors gracefully
        with pytest.warns(UserWarning, match="Failed to process"):
            results = processor.process_groups([corrupted_export])
        
        # Should continue processing other groups
        assert len(results) >= 0  # Some results may be skipped
    
    def test_memory_constraints(self, temp_config, large_export):
        """Test processing under memory constraints."""
        config = temp_config
        config.performance.memory_limit_mb = 100  # Low limit
        
        processor = UnifiedProcessor(config)
        
        # Should automatically use streaming mode
        with pytest.warns(UserWarning, match="Using streaming mode"):
            results = processor.process_groups([large_export])
        
        assert len(results) > 0
```

### 5. Development Environment Improvements

```python
# scripts/dev_setup.py
#!/usr/bin/env python3
"""Development environment setup script."""

def setup_dev_environment():
    """Set up complete development environment."""
    print("🚀 Setting up Egregora development environment...")
    
    # Install dependencies
    subprocess.run(["uv", "sync", "--dev"], check=True)
    
    # Generate test data
    generator = WhatsAppTestDataGenerator()
    test_data_dir = Path("tests/data/generated")
    test_data_dir.mkdir(exist_ok=True)
    
    # Create variety of test exports
    test_exports = [
        ("small_group", 3, 2, 20),
        ("medium_group", 8, 7, 50), 
        ("large_group", 15, 14, 100),
    ]
    
    for name, participants, days, msgs_per_day in test_exports:
        print(f"Generating {name}...")
        generator.generate_export(
            group_name=name,
            num_participants=participants,
            num_days=days,
            messages_per_day=msgs_per_day
        )
    
    # Set up pre-commit hooks
    subprocess.run(["pre-commit", "install"], check=True)
    
    # Create local config
    create_dev_config()
    
    print("✅ Development environment ready!")
    print("Run: pytest tests/ --benchmark-skip")
    print("Run: pytest tests/performance/ --benchmark-only")

if __name__ == "__main__":
    setup_dev_environment()
```

## Expected Benefits

1. **Faster Development**: Better test infrastructure speeds up iteration
2. **Higher Confidence**: More comprehensive testing reduces bugs
3. **Performance Awareness**: Benchmarks catch performance regressions
4. **Easier Onboarding**: Streamlined development setup
5. **Better Debugging**: Clearer test failures and more test data

## Acceptance Criteria

- [ ] Zero test warnings (filter out deprecation warnings)
- [ ] Realistic test data generation for various scenarios
- [ ] Performance benchmarks with regression detection
- [ ] Simple development environment setup script
- [ ] Integration tests covering main workflows
- [ ] Mock AI responses that match real API behavior
- [ ] Test coverage reporting and improvement

## Implementation Phases

### Phase 1: Test Infrastructure
- Clean up test warnings
- Improve AI mocking
- Add test data generation

### Phase 2: Performance Testing
- Benchmark suite
- Memory profiling
- Regression detection

### Phase 3: Development Experience
- Setup automation
- Better debugging tools
- Documentation improvements

## Files to Modify

- `tests/conftest.py` - Enhanced fixtures and mocking
- `tests/generators/` - Test data generation
- `tests/performance/` - Benchmark suite
- `scripts/dev_setup.py` - Development automation
- `pyproject.toml` - Test configuration
- `docs/development.md` - Development guide

## Related Issues

- #004: Dependency Management (test dependency updates)
- #005: Performance & Scalability (performance testing)
- #003: Error Messages & Debugging (test error scenarios)
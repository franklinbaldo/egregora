# Issue #004: Dependency Management

## Priority: Medium
## Effort: Low
## Type: Technical Debt

## Problem Description

Multiple dependency-related issues creating noise and potential future problems:

1. **Deprecated Dependencies**: 25+ warnings about deprecated libraries
2. **Version Compatibility**: Using outdated versions of key libraries
3. **Optional Dependencies**: Poor handling of optional AI providers
4. **Warning Spam**: Development warnings shown to end users

**Observed warnings during testing:**
```
DeprecationWarning: Use `GoogleModel` instead. See <https://ai.pydantic.dev/models/google/> for more details.
DeprecationWarning: `GoogleGLAProvider` is deprecated, use `GoogleProvider` with `GoogleModel` instead.
UnsupportedFieldAttributeWarning: The 'validate_default' attribute with value True was provided to the `Field()` function
```

## Current Behavior

### Dependency Issues
- Using deprecated `GoogleGLAProvider` (should use `GoogleProvider`)
- Outdated pydantic-ai integration patterns
- 25+ deprecation warnings during normal operation
- Version conflicts between AI libraries

### Poor Optional Dependency Handling
```python
try:
    from google import genai
except ImportError:
    # Silent failure, unclear error messages later
    genai = None
```

## Proposed Solution

### 1. Update Core Dependencies

**Priority updates:**
```toml
[project]
dependencies = [
    "pydantic-ai>=1.1.0",           # Latest stable
    "google-genai>=1.5.0",          # Updated API patterns  
    "llama-index-core>=0.15.0",     # Latest with fixes
    "pydantic>=2.10.0",             # Latest stable
]
```

### 2. Better Optional Dependency Management

```python
# src/egregora/providers/__init__.py
class AIProviderError(Exception):
    """Raised when AI provider is not available."""
    pass

def get_google_provider():
    """Get Google AI provider with clear error handling."""
    try:
        from google import genai
        from pydantic_ai.providers import GoogleProvider
        return GoogleProvider()
    except ImportError as e:
        raise AIProviderError(
            "Google AI not available. Install with: uv add google-genai"
        ) from e

# Usage with clear errors
try:
    provider = get_google_provider()
except AIProviderError as e:
    if config.demo_mode:
        provider = MockProvider()
    else:
        logger.error(f"AI Provider Error: {e}")
        raise
```

### 3. Pluggable AI Provider System

```python
# src/egregora/providers/base.py
class AIProvider(ABC):
    """Abstract base for AI providers."""
    
    @abstractmethod
    def generate_text(self, prompt: str, **kwargs) -> str:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass

# src/egregora/providers/google.py
class GoogleAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-flash-lite-latest"):
        self.client = genai.configure(api_key=api_key)
        self.model = model
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        # Updated to use latest Google AI patterns
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt)
        return response.text

# src/egregora/providers/mock.py  
class MockAIProvider(AIProvider):
    """Mock provider for demo mode."""
    
    def generate_text(self, prompt: str, **kwargs) -> str:
        return self.load_template_response(prompt)
```

### 4. Dependency Audit and Cleanup

**Audit current dependencies:**
```bash
# Check for outdated packages
uv show --outdated

# Security audit
uv audit

# Dependency tree analysis
uv tree
```

**Clean up unused dependencies:**
- Remove deprecated packages
- Consolidate overlapping functionality
- Update to latest stable versions

### 5. Better Error Messages for Missing Dependencies

```python
DEPENDENCY_HELP = {
    "google-genai": {
        "install": "uv add google-genai",
        "purpose": "Required for AI-powered post generation",
        "alternatives": ["Run with --demo-mode for testing"]
    },
    "mcp": {
        "install": "uv add mcp",
        "purpose": "Model Context Protocol server functionality", 
        "alternatives": ["Disable MCP in configuration"]
    }
}

def check_optional_dependencies():
    """Check and report on optional dependencies."""
    missing = []
    
    try:
        import google.genai
    except ImportError:
        missing.append("google-genai")
    
    if missing and not config.demo_mode:
        show_dependency_help(missing)
```

## Implementation Details

### Phase 1: Update Core Dependencies

1. **Audit current versions:**
   ```bash
   uv show --outdated
   ```

2. **Update pyproject.toml:**
   ```toml
   dependencies = [
       "pydantic-ai>=1.1.0",
       "google-genai>=1.5.0", 
       "llama-index-core>=0.15.0",
       # Remove deprecated packages
   ]
   ```

3. **Update code to use new APIs:**
   ```python
   # Old (deprecated)
   from pydantic_ai.providers import GoogleGLAProvider
   provider = GoogleGLAProvider()
   
   # New (recommended)
   from pydantic_ai.providers import GoogleProvider  
   from pydantic_ai.models import GoogleModel
   provider = GoogleProvider()
   model = GoogleModel("gemini-flash-lite-latest")
   ```

### Phase 2: Provider Abstraction

1. **Create provider interface:**
   - `src/egregora/providers/base.py`
   - `src/egregora/providers/google.py`
   - `src/egregora/providers/mock.py`

2. **Update configuration:**
   ```toml
   [llm]
   provider = "google"  # google, openai, anthropic, mock
   model = "gemini-flash-lite-latest"
   ```

3. **Factory pattern for providers:**
   ```python
   def create_ai_provider(config: LLMConfig) -> AIProvider:
       if config.provider == "google":
           return GoogleAIProvider(config.api_key, config.model)
       elif config.provider == "mock":
           return MockAIProvider()
       else:
           raise ValueError(f"Unknown provider: {config.provider}")
   ```

### Phase 3: Dependency Management Tools

1. **Add dependency check command:**
   ```bash
   egregora check-deps
   ```

2. **Runtime dependency validation:**
   ```python
   def validate_runtime_dependencies(config: PipelineConfig):
       """Validate dependencies are available for current config."""
       if config.enrichment.enabled and not has_google_genai():
           raise DependencyError("google-genai required for enrichment")
   ```

## Expected Benefits

1. **Cleaner Output**: No more deprecation warnings for users
2. **Future-Proof**: Using latest stable APIs
3. **Better Error Handling**: Clear messages for missing dependencies
4. **Extensibility**: Easy to add new AI providers
5. **Maintainability**: Easier to update dependencies

## Acceptance Criteria

- [ ] Zero deprecation warnings during normal operation
- [ ] All dependencies updated to latest stable versions
- [ ] Clear error messages for missing optional dependencies
- [ ] `egregora check-deps` command validates installation
- [ ] Mock provider works for demo mode
- [ ] Documentation updated with dependency requirements

## Files to Modify

- `pyproject.toml` - Update dependency versions
- `src/egregora/providers/` - New provider system
- `src/egregora/config.py` - Provider configuration
- `src/egregora/processor.py` - Use provider abstraction
- `docs/installation.md` - Updated requirements

## Related Issues

- #003: Error Messages & Debugging
- #001: Offline/Demo Mode  
- #011: Multi-User Support (for multiple provider support)
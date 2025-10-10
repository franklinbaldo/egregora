# Issue #003: Error Messages & Debugging

## Priority: High
## Effort: Low
## Type: UX Enhancement

## Problem Description

Error messages are often unhelpful, buried in stack traces, or provide no actionable guidance. This creates poor user experience and increases support burden.

**Examples of poor error messages:**

1. **API Key Error** (buried in 100+ line stack trace):
```
ClientError: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.'}}
```

2. **Dependency Warnings** (repeated 25+ times):
```
DeprecationWarning: Use `GoogleModel` instead. See <https://ai.pydantic.dev/models/google/> for more details.
```

3. **Configuration Issues** (unclear source):
```
AttributeError: 'PipelineConfig' object has no attribute 'directories'
```

## Current Behavior

### Stack Trace Overload
- Critical errors buried in technical stack traces
- No differentiation between user errors and system errors
- Development warnings shown to end users

### Poor Error Context
- No indication of which file or configuration caused the error
- No suggestions for how to fix issues
- Technical language instead of user-friendly messages

### No Progressive Debugging
- All-or-nothing error reporting
- No verbose mode for troubleshooting
- Hard to isolate specific component failures

## Proposed Solution

### 1. User-Friendly Error Handler

```python
class EgregoraErrorHandler:
    """Centralized error handling with user-friendly messages."""
    
    def handle_error(self, error: Exception, context: ErrorContext) -> None:
        if isinstance(error, ClientError) and "API key not valid" in str(error):
            self.show_api_key_error()
        elif isinstance(error, ConfigurationError):
            self.show_config_error(error, context)
        else:
            self.show_generic_error(error, context)
    
    def show_api_key_error(self) -> None:
        console.print(Panel.fit(
            "[red]❌ Invalid or missing Gemini API key[/red]\n\n"
            "[yellow]Quick fixes:[/yellow]\n"
            "1. Get a free API key: https://aistudio.google.com/app/apikey\n"
            "2. Set it: export GEMINI_API_KEY='your-key'\n"
            "3. Or run in demo mode: egregora --demo-mode\n\n"
            "[dim]Run 'egregora config validate' to check your setup[/dim]",
            title="🔑 API Key Error"
        ))
```

### 2. Layered Error Information

```bash
# Default: User-friendly message
❌ Failed to process group 'family-chat'
💡 Run with --verbose for technical details

# Verbose mode: Technical information
egregora --verbose
❌ Failed to process group 'family-chat'
📁 File: data/whatsapp_zips/family.zip
🔍 Parsing line 1247: "2024-03-15, 14:23 - Mom: <Media omitted>"
💥 Error: Invalid timestamp format
📋 Stack trace: [technical details]
```

### 3. Contextual Error Messages

```python
class ErrorContext:
    def __init__(self, 
                 operation: str,
                 file_path: Optional[Path] = None,
                 line_number: Optional[int] = None,
                 group_name: Optional[str] = None):
        self.operation = operation
        self.file_path = file_path
        self.line_number = line_number
        self.group_name = group_name

# Usage
try:
    parse_whatsapp_export(zip_path)
except Exception as e:
    context = ErrorContext(
        operation="parsing WhatsApp export",
        file_path=zip_path,
        group_name=group.name
    )
    error_handler.handle_error(e, context)
```

### 4. Warning Management

```python
class WarningFilter:
    """Filter and categorize warnings for end users."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.development_warnings = [
            "DeprecationWarning",
            "PendingDeprecationWarning"
        ]
    
    def should_show(self, warning: Warning) -> bool:
        if self.verbose:
            return True
        
        # Hide development warnings from end users
        return type(warning).__name__ not in self.development_warnings
```

### 5. Error Recovery Suggestions

```python
ERROR_RECOVERY = {
    "API_KEY_INVALID": [
        "Get API key from https://aistudio.google.com/app/apikey",
        "Set environment variable: export GEMINI_API_KEY='your-key'",
        "Or run in demo mode: egregora --demo-mode"
    ],
    "GROUP_NOT_FOUND": [
        "Check ZIP file exists in configured directory",
        "Verify directory path in egregora.toml",
        "Run 'egregora --list' to see discovered groups"
    ],
    "INVALID_TIMESTAMP": [
        "Verify WhatsApp export language settings",
        "Check for corrupted chat file",
        "Try re-exporting the chat from WhatsApp"
    ]
}
```

## Implementation Details

### Enhanced CLI with Error Handling

```python
def main():
    try:
        # Main application logic
        result = run_pipeline(config)
    except EgregoraError as e:
        error_handler.handle_user_error(e)
        sys.exit(1)
    except Exception as e:
        if config.debug:
            raise  # Full stack trace in debug mode
        error_handler.handle_system_error(e)
        sys.exit(1)
```

### Error Classification

```python
class EgregoraError(Exception):
    """Base class for user-facing errors."""
    
    def __init__(self, message: str, recovery_suggestions: List[str] = None):
        self.message = message
        self.recovery_suggestions = recovery_suggestions or []

class ConfigurationError(EgregoraError):
    """Configuration-related errors."""
    pass

class APIError(EgregoraError):
    """External API errors."""
    pass

class DataError(EgregoraError):
    """Data parsing/processing errors."""
    pass
```

### Progressive Debugging Flags

```bash
# Standard output (default)
egregora

# Show warnings and additional context
egregora --verbose

# Full debugging information
egregora --debug

# Technical details for development
egregora --trace
```

## Expected Benefits

1. **Reduced Support Burden**: Users can self-diagnose common issues
2. **Better User Experience**: Clear, actionable error messages
3. **Faster Debugging**: Verbose modes for troubleshooting
4. **Professional Feel**: Polished error handling

## Acceptance Criteria

- [ ] Common errors show user-friendly messages with suggestions
- [ ] Stack traces hidden by default, shown only with --debug
- [ ] Development warnings filtered out for end users
- [ ] Contextual information (file, line, operation) included in errors
- [ ] --verbose flag provides additional debugging information
- [ ] Error messages include relevant documentation links

## Quick Wins (Immediate improvements)

1. **Wrap main() with try/catch** for top-level error handling
2. **Filter deprecation warnings** from end-user output
3. **Add --verbose flag** to CLI
4. **Create specific error for missing API key**
5. **Add recovery suggestions to common errors**

## Implementation Phases

### Phase 1: Basic Error Handling
- Centralized error handler
- User-friendly messages for common errors
- Warning filters

### Phase 2: Enhanced Context
- Error context tracking
- File/line information
- Recovery suggestions

### Phase 3: Advanced Debugging
- Structured logging
- Error analytics
- Interactive error resolution

## Files to Modify

- `src/egregora/__main__.py` - Wrap with error handler
- `src/egregora/errors.py` - New error classes and handler
- `src/egregora/config.py` - Configuration validation errors
- `src/egregora/processor.py` - Add error context
- `docs/troubleshooting.md` - Error documentation

## Related Issues

- #002: Configuration UX Issues
- #001: Offline/Demo Mode
- #004: Dependency Management
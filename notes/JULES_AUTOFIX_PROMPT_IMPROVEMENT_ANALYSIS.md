# Jules Auto-Fix Prompt Improvement Analysis

## Executive Summary

This document analyzes improvements to the Jules Auto-Fix workflow prompt, applying the same principles developed for the Gemini PR review prompt improvements. The improved prompt transforms a minimal 20-line template into a comprehensive 400+ line guide that provides Jules with complete project context, coding standards, and testing philosophy.

---

## Current State Analysis

### Current Prompt (`.team/repo/templates/autofix_prompt.jinja`)

**Strengths:**
- ✅ Minimal and focused on immediate issues
- ✅ Provides CI logs and conflict information
- ✅ Clear structure with Jinja templating

**Critical Gaps:**
- ❌ **No project context** - Jules doesn't know about Egregora's architecture
- ❌ **No V2/Pure separation guidance** - Risk of mixing architectures
- ❌ **No testing philosophy** - May write implementation-focused tests
- ❌ **No coding standards** - Missing banned imports, line length, type annotation requirements
- ❌ **No error handling guidance** - Risk of adding defensive code that hides errors
- ❌ **No over-engineering warnings** - May add unnecessary abstractions
- ❌ **No commit history context** - Doesn't understand PR evolution
- ❌ **Generic failure description** - Just lists what failed, not how to think about fixes

**Current Length:** ~20 lines

**Token Count:** ~150 tokens

---

## Improvement Principles Applied

These principles were established through iterative refinement of the Gemini PR review prompt:

### 1. **Comprehensive Over Token-Optimized**
- **Rationale**: Token costs are negligible compared to the value of correct fixes
- **Implementation**: Expanded from 20 lines to 400+ lines with detailed guidance
- **Impact**: Jules gets full context to make informed decisions

### 2. **V2/Main Architecture Separation**
- **Rationale**: Critical architectural constraint that MUST NOT be violated
- **Implementation**: Prominent section with clear rules about mixing V2/Pure
- **Impact**: Prevents architectural violations in fixes

### 3. **TDD and Behavior-Focused Testing**
- **Rationale**: Tests should validate behavior, not implementation details
- **Implementation**: Comprehensive examples of good vs bad tests
- **Impact**: Jules writes maintainable, refactor-safe tests

### 4. **Code-First Philosophy**
- **Rationale**: PR descriptions become stale; code + commits are authoritative
- **Implementation**: Explicit source priority ordering
- **Impact**: Jules trusts code changes over potentially outdated descriptions

### 5. **Specific Error Propagation**
- **Rationale**: Defensive code hides errors; specific errors enable iterative debugging
- **Implementation**: Examples of good error handling vs defensive anti-patterns
- **Impact**: Failures produce actionable error messages

### 6. **Avoid Over-Engineering**
- **Rationale**: Balance between good abstractions and unnecessary complexity
- **Implementation**: Clear distinction between helpful refactoring and premature optimization
- **Impact**: Jules makes pragmatic decisions about when to abstract

### 7. **Project-Specific Standards**
- **Rationale**: Egregora has specific patterns (banned imports, Ibis over Pandas)
- **Implementation**: Explicit lists of allowed/banned imports and patterns
- **Impact**: Fixes pass CI checks on first try

### 8. **Commit History Understanding**
- **Rationale**: Commits tell the story of what was attempted and why
- **Implementation**: Guidance on reading commit patterns and evolution
- **Impact**: Jules understands context beyond just the current failure

---

## Improved Prompt Structure

### New Sections Added

#### 1. **📋 Project Overview: Egregora** (Lines 3-28)
- **Purpose**: Provide architectural context
- **Content**:
  - V2/Pure separation (CRITICAL RULE)
  - Technology stack (DuckDB, Ibis, Pydantic-AI, LanceDB)
  - Core principles (functional transformations, type safety)

**Example:**
```markdown
**🚨 CRITICAL RULE: New code should use Pure types when available.
NEVER mix V2 and Pure imports in the same module. This is a critical violation.**
```

#### 2. **🛠️ Code Standards and Patterns** (Lines 63-110)
- **Purpose**: Prevent common CI failures
- **Content**:
  - Banned imports (pandas, pyarrow, relative imports)
  - Line length limits (110 for Ruff, 100 for Black)
  - Type annotation requirements
  - Error handling patterns with examples

**Impact**: Jules knows exactly what will fail CI before pushing

#### 3. **🧪 Testing Philosophy: TDD and Behavior Focus** (Lines 112-223)
- **Purpose**: Guide test quality
- **Content**:
  - Behavior vs implementation testing principles
  - 6 detailed examples (good vs bad)
  - When mocking is acceptable
  - Observable outcomes focus

**Key Example:**
```python
# ✅ GOOD - Behavior-focused
def test_filters_out_system_messages():
    messages = [
        {"content": "User message", "type": "user"},
        {"content": "System alert", "type": "system"}
    ]
    result = process_messages(messages)
    assert len(result) == 1  # Observable behavior
    assert result[0]["type"] == "user"

# ❌ BAD - Implementation-focused
def test_process_messages_calls_filter():
    with mock.patch('module.filter_system') as mock_filter:
        process_messages(messages)
        mock_filter.assert_called_once()  # Testing HOW, not WHAT!
```

#### 4. **🏗️ Common Patterns** (Lines 225-270)
- **Purpose**: Show idiomatic egregora code
- **Content**:
  - Functional data transformations with Ibis
  - Pydantic validation patterns
  - Configuration management

**Impact**: Jules writes code that matches project style

#### 5. **⚠️ What to AVOID** (Lines 272-390)
- **Purpose**: Prevent common anti-patterns
- **Content**:
  - Over-engineering vs good abstractions (with examples)
  - Defensive programming pitfalls
  - Unnecessary error handling
  - Documentation overkill
  - Backwards compatibility hacks

**Key Distinction:**
```python
# GOOD abstraction - reduces duplication
def parse_whatsapp_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%m/%d/%y, %H:%M")

# BAD over-engineering - hypothetical future needs
class DateParserFactory:
    def create_parser(self, format_type: str) -> DateParser:
        # ... 50 lines of unnecessary abstraction
```

#### 6. **🔍 Understanding the PR Context** (Lines 392-422)
- **Purpose**: Guide context gathering
- **Content**:
  - Source priority ordering (code > commits > description)
  - Commit history pattern recognition
  - Why PR descriptions become stale

**Impact**: Jules doesn't blindly trust outdated PR descriptions

#### 7. **✅ Your Checklist** (Lines 424-436)
- **Purpose**: Final verification before pushing
- **Content**: 8-point checklist covering all critical requirements
- **Impact**: Systematic verification reduces iteration cycles

#### 8. **🚀 Execution Guidance** (Lines 438-479)
- **Purpose**: Systematic fix approach
- **Content**:
  - 5-step process (understand → review → fix → test → clean up)
  - Commit message format
  - Root cause vs symptom analysis

**Impact**: Jules follows disciplined debugging methodology

---

## Comparison: Current vs Improved

| Aspect | Current Prompt | Improved Prompt |
|--------|---------------|-----------------|
| **Length** | ~20 lines | ~400 lines |
| **Token Count** | ~150 tokens | ~3500 tokens |
| **Project Context** | None | Comprehensive (V2/Pure, tech stack) |
| **Code Standards** | None | Complete (imports, types, formatting) |
| **Testing Guidance** | None | TDD philosophy with examples |
| **Error Handling** | None | Specific propagation vs defensive code |
| **Anti-Patterns** | None | 5 categories with examples |
| **Commit Context** | None | Source priority and evolution |
| **Egregora-Specific** | Generic | Ibis, DuckDB, Pydantic-AI patterns |
| **Verification** | None | 8-point checklist |
| **Execution Process** | Implicit | Explicit 5-step methodology |

---

## Expected Differences in Jules Behavior

### Before (Current Prompt)

**Scenario**: CI fails due to `import pandas as pd`

**Jules might:**
1. See the import error in logs
2. Fix the specific import
3. Not realize other pandas usage exists
4. Push changes that fail again with different pandas errors
5. Add defensive try-catch around imports

**Result**: Multiple iteration cycles, defensive code added

---

### After (Improved Prompt)

**Scenario**: Same CI failure due to pandas import

**Jules will:**
1. See the import error
2. **Know from prompt**: Pandas is BANNED, must use Ibis instead
3. Search entire codebase for ALL pandas usage
4. Convert all pandas operations to Ibis expressions
5. Verify no defensive code hiding errors
6. Run full test suite before pushing

**Result**: Single iteration, clean fix, proper patterns

---

## Specific Improvements by Category

### 1. Architecture Violations

**Current**: Jules might mix V2/Pure without knowing it's wrong

**Improved**:
```markdown
🚨 CRITICAL RULE: NEVER mix V2 and Pure imports in the same module
```
Jules knows this is a critical violation and checks imports carefully

### 2. Test Quality

**Current**: Jules might write implementation-focused tests
```python
# Jules might write this (BAD)
def test_calls_filter_function():
    with mock.patch('filter') as m:
        process()
        m.assert_called_once()
```

**Improved**: Jules writes behavior-focused tests
```python
# Jules will write this (GOOD)
def test_filters_system_messages():
    result = process(messages)
    assert len(result) == 1
    assert result[0]["type"] == "user"
```

### 3. Error Handling

**Current**: Jules might add defensive code
```python
# Jules might write this (BAD)
try:
    result = dangerous_operation()
except Exception as e:
    print(f"Error: {e}")
    return None
```

**Improved**: Jules lets errors propagate
```python
# Jules will write this (GOOD)
def load_config(path: Path) -> Config:
    if not path.exists():
        raise ConfigurationError(f"CONFIG_NOT_FOUND: {path}")
    return Config.from_file(path)  # Let errors propagate
```

### 4. Over-Engineering

**Current**: Jules might add unnecessary abstractions

**Improved**: Jules distinguishes good from bad abstraction
- ✅ Extract function used in 3+ places
- ❌ Build framework for single use case

### 5. Commit Understanding

**Current**: Jules only sees PR description (potentially stale)

**Improved**: Jules reads commit history to understand:
- What was attempted initially
- What changed through reviews
- Why certain decisions were made

---

## Implementation Strategy

### Phase 1: Safe Deployment (Recommended)

1. **Keep both templates**:
   - `autofix_prompt.jinja` (current)
   - `autofix_prompt_improved.jinja` (new)

2. **Add environment variable toggle**:
   ```python
   # In auto_fix.py
   use_improved = os.getenv("JULES_USE_IMPROVED_PROMPT", "false") == "true"
   template_name = "autofix_prompt_improved.jinja" if use_improved else "autofix_prompt.jinja"
   ```

3. **Test on select PRs**:
   - Enable improved prompt for Jules-created PRs first
   - Monitor success rate and iteration cycles
   - Gradually expand to all PRs

4. **Metrics to track**:
   - Average iterations to fix (expect reduction)
   - CI pass rate on first push (expect increase)
   - Types of errors (should shift from standards to logic)

### Phase 2: Full Deployment

1. **After 1-2 weeks of testing**:
   - If metrics improve → replace old template
   - If neutral → keep improved as default
   - If worse → analyze why and iterate

2. **Update workflow**:
   - Remove environment variable toggle
   - Make improved version the default
   - Archive old template for reference

### Phase 3: Continuous Improvement

1. **Learn from failures**:
   - When Jules still needs multiple iterations, analyze why
   - Add specific guidance for recurring issues
   - Refine examples based on actual errors

2. **Community feedback**:
   - Collect feedback from PR authors
   - Identify gaps in guidance
   - Update prompt based on patterns

---

## Risk Analysis

### Low Risk

- **Token costs**: Negligible (~$0.003 per fix with current pricing)
- **Performance**: No latency impact (prompt is static)
- **Compatibility**: Drop-in replacement (same variables)

### Medium Risk

- **Prompt complexity**: More to read, but Jules handles long context well
- **Over-guidance**: Risk of Jules becoming too rigid
  - **Mitigation**: Balanced language ("prefer" vs "must")

### High Risk (Mitigated)

- **Breaking existing fixes**: Changing behavior mid-fix
  - **Mitigation**: Only applies to NEW fix sessions
- **Divergence from standards**: If CLAUDE.md updates
  - **Mitigation**: CI checks enforce standards regardless

---

## Success Metrics

### Quantitative

1. **Iteration cycles**: Expect 20-30% reduction
   - Current baseline: ~2.5 iterations per fix (estimated)
   - Target: <2 iterations per fix

2. **CI pass rate**: Expect 30-40% increase on first push
   - Current baseline: ~60% (estimated)
   - Target: >80%

3. **Types of failures**:
   - Decrease: Import errors, type errors, formatting
   - Stable: Logic errors, edge cases

### Qualitative

1. **Code quality**: Matches project patterns
2. **Test quality**: Behavior-focused, maintainable
3. **Commit messages**: Clear, follows format
4. **PR comments**: Jules explains reasoning better

---

## Conclusion

The improved Jules autofix prompt applies the same comprehensive, context-rich approach that proved successful for the Gemini PR review prompt. By providing complete project context, coding standards, testing philosophy, and anti-pattern warnings, Jules can make better decisions autonomously and reduce iteration cycles.

**Key Innovation**: Rather than minimal instructions, we front-load comprehensive guidance. This enables Jules to "think" like a senior egregora contributor from the start, rather than learning through failed iterations.

**Recommended Action**: Deploy in Phase 1 (toggle mode) to validate improvements with real data, then proceed to full deployment if metrics confirm benefits.

---

**Document Version**: 1.0
**Last Updated**: 2026-01-02
**Related Documents**:
- `GEMINI_PROMPT_IMPROVEMENT_ANALYSIS.md`
- `CLAUDE.md`
- `.team/repo/templates/autofix_prompt_improved.jinja`

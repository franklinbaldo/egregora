# PR #564 Code Review: File-Based Agent System

**Reviewer:** Claude (AI Code Review)
**Date:** 2025-11-04
**PR:** https://github.com/franklinbaldo/egregora/pull/564
**Branch:** `feature-file-based-agents` → `main`
**Status:** Draft (Open)
**Author:** google-labs-jules (bot)

## Executive Summary

This PR introduces a sophisticated file-based agent system for Egregora, allowing flexible agent definitions through Jinja templates with YAML front-matter. The implementation includes agent resolution, tool/skill registries, and CLI management commands. The architecture is well-designed and aligns with Egregora's modular design philosophy, but there are **critical bugs** that must be fixed before merging.

**Recommendation:** ⚠️ **REQUEST CHANGES** - Critical bugs must be fixed before merge.

---

## Overview

### What This PR Does

- Implements file-based agent system with Jinja templates + YAML front-matter
- Adds agent resolver with precedence: post → section → default
- Creates tool/skill registries with profile-based management
- Refactors editor to use `pydantic-ai` framework
- Adds CLI commands: `egregora agents list`, `egregora agents explain`, `egregora agents lint`
- Includes configuration hashing for change detection

### Files Changed

- **18 files changed**: +749 additions, −380 deletions
- **New modules**: `src/egregora/agents/` (loader, models, registry, resolver, tools)
- **Modified**: `src/egregora/generation/editor/agent.py`, `src/egregora/orchestration/cli.py`
- **Config files**: `.egregora/` directory with agents, tools, skills, and global settings

---

## Test Results

✅ **All 6 tests pass:**
```bash
tests/test_agents.py::test_load_agent PASSED
tests/test_agents.py::test_tool_registry PASSED
tests/test_agents.py::test_agent_resolver PASSED
tests/test_agents.py::test_cli_agents_list PASSED
tests/test_agents.py::test_cli_agents_explain PASSED
tests/test_agents.py::test_cli_agents_lint PASSED
```

❌ **Linting errors found:** 39 errors across agents/ and editor integration

---

## Critical Issues (Must Fix)

### 🔴 1. Missing Import: `hashlib` in `agent.py`

**Location:** `src/egregora/generation/editor/agent.py:85`

```python
prompt_render_hash = hashlib.sha256(prompt.encode()).hexdigest()
```

**Error:** `F821 Undefined name 'hashlib'`

**Impact:** Runtime crash when running editor sessions.

**Fix:**
```python
# Add to imports at top of file
import hashlib
```

### 🔴 2. Incorrect Type Annotation in `agent.py`

**Location:** `src/egregora/generation/editor/agent.py:47`

```python
client: "genai.Client",
```

**Error:** `F821 Undefined name 'genai'`

**Impact:** Type checking failures, potential runtime issues.

**Fix:**
```python
# Add proper import
from google import genai

# Then use proper type annotation
client: genai.Client,
```

### 🔴 3. Unused Import in `agent.py`

**Location:** `src/egregora/generation/editor/agent.py:6`

```python
from jinja2 import Environment, FileSystemLoader
```

**Error:** `F401 'jinja2.Environment' imported but unused`

**Impact:** Dead code, confusing imports (SandboxedEnvironment is used instead).

**Fix:**
```python
# Remove Environment from import since only SandboxedEnvironment is used
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
```

---

## Major Issues (Should Fix Before Merge)

### 🟡 4. Outdated Type Hints (Python 3.12+ Style)

**Files:** All files in `src/egregora/agents/`

The code uses deprecated typing imports (`Dict`, `List`, `Set`, `Any`) instead of modern Python 3.12+ built-in types.

**Examples:**
```python
# ❌ Old style (deprecated)
from typing import List, Dict, Any
def foo(x: Dict[str, Any]) -> List[str]:
    ...

# ✅ New style (Python 3.12+)
def foo(x: dict[str, Any]) -> list[str]:
    ...
```

**Affected:**
- `models.py`: 12 occurrences
- `registry.py`: 14 occurrences
- `resolver.py`: 2 occurrences
- `tools.py`: 1 occurrence

**Fix:** Run `uv run ruff check --fix src/egregora/agents/` to auto-fix most of these.

### 🟡 5. Import Sorting Issues

**Files:** All files in `src/egregora/agents/` + `agent.py`

**Error:** `I001 Import block is un-sorted or un-formatted`

**Fix:** Run `uv run ruff check --fix` to auto-sort imports.

### 🟡 6. Unused Import in `registry.py`

**Location:** `src/egregora/agents/registry.py:4`

```python
from dataclasses import dataclass, field  # 'field' is unused
```

**Fix:**
```python
from dataclasses import dataclass
```

### 🟡 7. Editor Agent Integration Issues

**Location:** `src/egregora/generation/editor/agent.py:41-111`

**Issues:**
1. **Too many arguments** (8 > 5): `PLR0913` - Function signature too complex
2. **Missing error handling**: No try/except around agent execution
3. **Incomplete integration**: The agent result handling assumes specific output structure but doesn't validate it

**Suggested Fix:**
```python
# Consider wrapping related params in a config object
@dataclass
class EditorSessionConfig:
    post_path: Path
    model_config: ModelConfig
    egregora_path: Path
    docs_path: Path
    rag_dir: Path
    client: genai.Client
    context: dict[str, Any] | None = None
    agent_override: str | None = None

async def run_editor_session(config: EditorSessionConfig) -> EditorResult:
    ...
```

---

## Minor Issues (Nice to Have)

### 🟢 8. Missing Docstrings

**Files:** Most functions in `agents/` modules lack docstrings.

**Examples:**
- `agents/registry.py`: Classes and methods lack docstrings
- `agents/resolver.py`: Functions have minimal documentation
- `agents/tools.py`: Tool functions have minimal docstrings

**Recommendation:** Add comprehensive docstrings following Egregora's documentation standards (see `CLAUDE.md`).

### 🟢 9. Incomplete Tool Implementation

**Location:** `src/egregora/agents/tools.py`

```python
def finish(expect_version: int, decision: str, notes: str) -> None:
    """Mark editing complete."""
    pass  # No implementation!
```

**Issue:** The `finish` tool does nothing. It should interact with the editor object.

**Also:**
```python
def diversity_sampler(k: int, seed: int) -> str:
    """Sample diverse content based on a given seed."""
    return f"Sampled {k} items with seed {seed}."  # Dummy implementation
```

**Recommendation:** Either implement these properly or mark them as TODO/placeholder with clear comments.

### 🟢 10. Security: Sandboxed Jinja Environment

**Location:** `src/egregora/generation/editor/agent.py:63`

```python
jinja_env = SandboxedEnvironment(loader=FileSystemLoader(str(egregora_path)))
```

✅ **Good:** Uses `SandboxedEnvironment` instead of regular `Environment`.

**However:** Consider adding explicit security policies:
```python
jinja_env = SandboxedEnvironment(
    loader=FileSystemLoader(str(egregora_path)),
    autoescape=True,  # Prevent XSS if templates render user input
)
```

### 🟢 11. Magic Model in Agent Templates

**Location:** `.egregora/agents/curator.jinja:3`

```yaml
model: gpt-5-thinking
```

**Issue:** `gpt-5-thinking` is not a real model (yet?). Should this be `gemini-2.5-thinking` or similar?

**Also:** `.egregora/agents/_default.jinja:3` uses `gpt-4-turbo` (OpenAI model) but Egregora uses Gemini.

**Recommendation:** Verify model names match actual available models in Egregora's model config.

### 🟢 12. Test Coverage Gaps

**Current tests:** Basic happy-path tests only.

**Missing test cases:**
- Error handling (invalid YAML, missing files)
- Variable merging with disallowed keys
- Tool profile conflicts (allow + deny)
- Agent hash collision detection
- Malformed front-matter in `.jinja` files
- Editor integration with actual LLM calls (or mocked)

**Recommendation:** Add negative test cases and edge cases.

---

## Architecture Review

### ✅ Strengths

1. **Clean Separation of Concerns**: Loader, resolver, registry, and tools are well-separated
2. **Pydantic Validation**: Using Pydantic models for config validation is excellent
3. **Extensibility**: Easy to add new agents, tools, and skills without code changes
4. **Precedence System**: Post → section → default precedence is intuitive and powerful
5. **Security-First**: Uses `SandboxedEnvironment` and variable allowlists
6. **Hashing for Change Detection**: SHA256 hashes enable cache invalidation and versioning
7. **Follows Egregora Philosophy**: "Trust the LLM" - gives AI control through structured config

### ⚠️ Concerns

1. **Complexity Jump**: This adds significant complexity to the editor workflow
2. **Documentation**: No user-facing docs explaining how to create/use agents
3. **Migration Path**: What happens to existing posts/sites without `.egregora/` directories?
4. **Tool Dependency Injection**: The pydantic-ai integration feels incomplete (see editor issues)
5. **Unused Config Fields**: Some fields like `ttl`, `env.timezone` are defined but not clearly used

### 🔍 Questions for Author

1. **Model naming**: Why `gpt-4-turbo` and `gpt-5-thinking` instead of Gemini models?
2. **TTL field**: How is the `ttl` field in agent config used? Not referenced in code.
3. **Env variables**: How are `env` variables from agent config exposed to prompts?
4. **Skills vs Tools**: What's the distinction? Skills seem to be Jinja macros, tools are Python functions?
5. **Migration strategy**: How should existing Egregora users adopt this system?

---

## Detailed Code Analysis

### `agents/models.py` - Pydantic Models ✅

**Strengths:**
- Clean Pydantic models with proper defaults
- Good use of `Field(default_factory=dict)`

**Issues:**
- Outdated type hints (see Issue #4)

### `agents/loader.py` - Agent Loading ✅

**Strengths:**
- Robust regex for front-matter extraction
- Good error messages

**Suggestion:**
```python
# Consider adding validation for malformed YAML
try:
    config_dict = yaml.safe_load(front_matter_str)
    agent_config = AgentConfig(**config_dict)
except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML in {agent_path}: {e}") from e
except ValidationError as e:
    raise ValueError(f"Invalid agent config in {agent_path}: {e}") from e
```

### `agents/resolver.py` - Agent Resolution ✅

**Strengths:**
- Clear precedence logic
- Good warning message for disallowed variables

**Improvement:**
```python
# Line 46: Use logging instead of print
logger.warning(
    f"Variable '{key}' from {post_path.name} is not allowed by agent "
    f"'{agent_config.agent_id}' and will be ignored."
)
```

### `agents/registry.py` - Tool/Skill Registries ⚠️

**Strengths:**
- Clean separation of tools and skills
- Profile-based tool management is powerful

**Issues:**
- `_normalize_and_hash` comment says "more robust implementation would deeply sort keys" but doesn't
- No validation that referenced profiles actually exist

**Improvement:**
```python
def resolve_toolset(self, agent_tools_config) -> Set[str]:
    toolset = set()
    for profile_name in agent_tools_config.use_profiles:
        if profile_name not in self._profiles:
            logger.warning(f"Profile '{profile_name}' not found, skipping")
            continue
        profile = self._profiles[profile_name]
        # ...rest
```

### `agents/tools.py` - Tool Implementations ⚠️

**Critical Issue:** Several tools are stubs or incomplete (see Issue #9).

**Architectural Concern:** Tools need access to dependencies (editor, client, etc.) but the current design uses function signatures that expect these as parameters. With pydantic-ai, tools should receive dependencies from the agent's dependency injection system, not as direct parameters.

**Example of proper pydantic-ai tool:**
```python
from pydantic_ai import Tool

@tool
async def query_rag(query: str, max_results: int = 5, ctx: RunContext) -> str:
    """RAG search returning formatted context string."""
    rag_dir = ctx.deps["rag_dir"]
    client = ctx.deps["client"]
    # ... implementation
```

### Editor Integration - `generation/editor/agent.py` 🔴

**Critical Issues:** See Issues #1, #2, #3, #7.

**Major Refactor:** This file was completely rewritten from ~160 lines to ~30 lines, replacing a working Gemini function-calling implementation with pydantic-ai. While this is a good direction, the implementation is incomplete:

1. **Missing error handling** around agent execution
2. **Incomplete agent result handling**: Assumes `result.output` has specific keys without validation
3. **Tool registration unclear**: How do tools get access to dependencies?
4. **Lost functionality**: Previous implementation had detailed logging, retry logic, and conversation history management - where did this go?

**Recommendation:** Either complete the pydantic-ai integration properly or consider doing this refactor in a separate PR.

---

## Compliance with CLAUDE.md Standards

### ✅ Follows

- **Ibis-First**: No pandas imports (not applicable to this PR)
- **Testing**: Tests included and passing
- **Code organization**: Modular design in staged architecture
- **Python 3.12+**: Uses modern features

### ❌ Violations

- **Linting**: 39 ruff errors (see Issues #4, #5, #6)
- **Type hints**: Uses deprecated `typing.Dict` instead of `dict`
- **Documentation**: Missing docstrings and user docs

---

## Recommendations

### Before Merge (Critical)

1. ✅ **Fix all Critical Issues (#1, #2, #3)** - These cause runtime failures
2. ✅ **Fix linting errors** - Run `uv run ruff check --fix src/egregora/agents/`
3. ✅ **Add missing imports and remove unused ones**
4. ✅ **Verify model names** in agent templates match Egregora's config
5. ✅ **Add error handling** to editor integration

### Immediate Next Steps (High Priority)

1. 📝 **Write user documentation** - How to create agents, tools, and skills
2. 🧪 **Add edge case tests** - Error handling, malformed configs
3. 🔧 **Complete tool implementations** - `finish()`, `diversity_sampler()` are stubs
4. 📖 **Add docstrings** to all public functions and classes
5. ♻️ **Consider refactoring** `run_editor_session` to reduce complexity

### Future Improvements (Nice to Have)

1. 🔐 **Enhanced security**: Add explicit Jinja autoescape policies
2. 📊 **Metrics**: Log agent selection, tool usage, hash changes
3. 🎨 **Pretty-print**: Improve CLI output formatting (tables, colors)
4. 🧩 **Schema validation**: JSON Schema for agent templates
5. 📚 **Examples**: Add example agents for common use cases

---

## Testing Checklist

Run these commands before merging:

```bash
# 1. Run all tests
uv run pytest tests/test_agents.py -v

# 2. Fix linting errors
uv run ruff check --fix src/egregora/agents/
uv run ruff check --fix src/egregora/generation/editor/agent.py

# 3. Verify no remaining errors
uv run ruff check src/egregora/

# 4. Run full test suite
uv run pytest tests/

# 5. Test CLI commands manually
uv run egregora agents list
uv run egregora agents explain curator
uv run egregora agents lint

# 6. Test editor integration (requires API key)
export GOOGLE_API_KEY="your-key"
uv run egregora edit docs/posts/test-post.md --agent curator
```

---

## Summary

This PR introduces a powerful and well-architected agent system that significantly enhances Egregora's flexibility. The design is sound and aligns with the project's philosophy. However, **critical bugs** in the editor integration will cause runtime failures and must be fixed before merge.

### Action Items for Author (Jules)

#### 🔴 Blocking (Must Fix)
- [ ] Add missing `import hashlib` to `agent.py`
- [ ] Fix `genai` type annotation in `agent.py`
- [ ] Remove unused `Environment` import from `agent.py`
- [ ] Run `ruff check --fix` on all agent files

#### 🟡 Important (Should Fix)
- [ ] Update type hints to Python 3.12+ style (dict, list, set)
- [ ] Add error handling to `run_editor_session()`
- [ ] Verify model names in agent templates
- [ ] Complete or document stub implementations in `tools.py`

#### 🟢 Optional (Nice to Have)
- [ ] Add user documentation for agent system
- [ ] Add docstrings to all public APIs
- [ ] Expand test coverage for edge cases
- [ ] Consider refactoring `run_editor_session` to reduce complexity

**Estimated effort to address blockers:** ~30 minutes

**Overall assessment:** ⭐⭐⭐⭐☆ (4/5) - Excellent architecture, needs bug fixes before merge.

---

## Reviewer Notes

This review was conducted using:
- Static analysis (ruff linting)
- Test execution (pytest)
- Code reading and architectural analysis
- Comparison with Egregora's design principles from CLAUDE.md

The review assumes Jules (Google's AI coding agent) will address these issues. Given Jules' track record in this repo, I'm confident these fixes will be completed promptly.

**Recommendation:** Request changes, re-review after fixes applied.

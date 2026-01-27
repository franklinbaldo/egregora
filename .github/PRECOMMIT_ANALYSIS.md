# Pre-commit Configuration Analysis

> Generated: 2026-01-27 | Updated after cleanup

## Executive Summary

The repository has **1 config file** with **58 lines** orchestrating **17 hooks** across **3 sources**.

**Architecture:** Multi-layered Quality Gate System
- External hooks for standard checks (ruff, pre-commit-hooks)
- Local hooks for project-specific validation

---

## Hook Inventory

| Source | Hooks | Purpose |
|--------|-------|---------|
| `ruff-pre-commit` | 2 | Linting + formatting |
| `pre-commit-hooks` | 11 | Standard file validations |
| `local` | 4 | Project-specific rules |
| **Total** | **17** | |

---

## Hook Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PRE-COMMIT PIPELINE (58 lines)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STAGE 1: RUFF (astral-sh/ruff-pre-commit v0.14.7)                   │   │
│   │                                                                     │   │
│   │  ruff check ──► Auto-fix with --unsafe-fixes                        │   │
│   │  ruff format ──► Code formatting                                    │   │
│   │                                                                     │   │
│   │  Config: pyproject.toml [tool.ruff]                                 │   │
│   │  • Line length: 110                                                 │   │
│   │  • Target: Python 3.12                                              │   │
│   │  • Rules: ALL (with 40+ strategic ignores)                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STAGE 2: STANDARD HOOKS (pre-commit/pre-commit-hooks v4.6.0)        │   │
│   │                                                                     │   │
│   │  ├── check-added-large-files (max 2MB)                              │   │
│   │  ├── check-ast                                                      │   │
│   │  ├── check-case-conflict                                            │   │
│   │  ├── check-merge-conflict                                           │   │
│   │  ├── check-json                                                     │   │
│   │  ├── check-toml                                                     │   │
│   │  ├── check-yaml (multi-doc, unsafe)                                 │   │
│   │  ├── debug-statements                                               │   │
│   │  ├── end-of-file-fixer                                              │   │
│   │  ├── mixed-line-ending                                              │   │
│   │  └── trailing-whitespace                                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STAGE 3: LOCAL HOOKS (Project-Specific)                             │   │
│   │                                                                     │   │
│   │  vulture ──────────► Dead code detection (min-confidence=80%)       │   │
│   │  check-private-imports ──► No _private in __all__, cross-module     │   │
│   │  check-test-config ──────► No direct EgregoraConfig() in tests      │   │
│   │  check-lint-suppressions ► No noqa/type:ignore in src/              │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   Exclusions: ^(\.team/|artifacts/)                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Hook Analysis

### Stage 1: Ruff (Code Quality)

| Hook | Args | Impact |
|------|------|--------|
| `ruff` | `--fix --unsafe-fixes` | Auto-corrects linting issues, including unsafe transformations |
| `ruff-format` | (none) | Consistent code formatting |

**Ruff Configuration Highlights:**

```
Line Length: 110 characters
Target: Python 3.12
Rules: ALL with strategic ignores
```

**Key Ignored Rules:**
- Formatter conflicts (`COM812`, `ISC001`, `Q*`, `W191`)
- Interface args (`ARG001/002/005`)
- Complexity metrics (`C901`, `PLR*`) - can be re-enabled if needed
- Type-checking imports (`TC*`) - Pydantic needs runtime access

**Banned Imports:**
- `pandas` → Use ibis-framework
- `pyarrow` → Use ibis-framework

---

### Stage 2: Standard Hooks (File Hygiene)

| Hook | Purpose | Config |
|------|---------|--------|
| `check-added-large-files` | Prevent binary bloat | maxkb=2000 |
| `check-ast` | Validate Python syntax | - |
| `check-case-conflict` | Cross-platform filename safety | - |
| `check-merge-conflict` | No merge markers | - |
| `check-json` | Valid JSON | - |
| `check-toml` | Valid TOML | - |
| `check-yaml` | Valid YAML | multi-doc, unsafe |
| `debug-statements` | No breakpoint(), pdb | - |
| `end-of-file-fixer` | Trailing newline | - |
| `mixed-line-ending` | Consistent EOL | - |
| `trailing-whitespace` | Clean trailing spaces | - |

---

### Stage 3: Local Hooks (Project Rules)

#### 1. **vulture** - Dead Code Detection

```yaml
entry: uv run vulture
args: ["src", "tests", "tests/vulture_whitelist.py", "--min-confidence=80"]
```

**Purpose:** Find unused code with 80% confidence threshold

**Whitelist:** `tests/vulture_whitelist.py`
- Context manager protocol params (`exc_type`, `exc_val`, `exc_tb`)
- Mock method parameters
- Protocol signatures

---

#### 2. **check-private-imports** - Encapsulation Guard

```
Location: scripts/dev_tools/check_private_imports.py
Types: [python]
```

**Rules:**
1. No `_private` names in `__all__`
2. No cross-module imports of `_private` functions

**Skipped:** Test files (tests often need internal access)

---

#### 3. **check-test-config** - Test Isolation

```
Location: scripts/dev_tools/check_test_config.py
Files: tests/.*\.py$
```

**Violations:**
| Pattern | Message |
|---------|---------|
| `EgregoraConfig()` | Use test_config fixture |
| `RAGSettings()` | Use test_rag_settings fixture |
| `ModelSettings()` | Use test_model_settings fixture |
| `Path(".egregora/` | Use tmp_path fixture |

---

#### 4. **check-lint-suppressions** - No Inline Suppressions

```
Location: scripts/dev_tools/check_lint_suppressions.py
Files: ^src/
```

**Blocked Patterns:**
- `# noqa`
- `# type: ignore`
- `# pylint: disable`
- `# pyright: ignore`

**Allowed Files:**
- `src/egregora/agents/writer.py` (external untyped imports)

**Philosophy:** Use `pyproject.toml [tool.ruff.lint.per-file-ignores]` instead of inline suppressions

---

## Per-File Ignores Summary

| Path Pattern | Ignores | Reason |
|--------------|---------|--------|
| `tests/**/*.py` | S101, PLR2004, ANN, D, INP001, S311, S324, S603, S607, S506, S108, PT009, PT017, SIM117, PERF401 | Testing patterns |
| `src/egregora/cli/*.py` | B008 | Typer Option() defaults |
| `src/egregora/cli/diagnostics.py` | BLE001, S603 | Fault-tolerant diagnostics |
| `src/egregora/database/profile_cache.py` | BLE001 | Cache fault tolerance |
| `src/egregora/orchestration/*.py` | BLE001 | Worker fault tolerance |
| `src/egregora/rag/*.py` | BLE001 | RAG fault tolerance |
| `src/egregora/output_sinks/mkdocs/scaffolding.py` | S506 | Trusted YAML source |
| `src/egregora/ops/media.py` | PTH122 | os.path for extensions |
| `src/egregora/knowledge/profiles.py` | PTH118, PTH123 | Performance optimization |

---

## Global Exclusions

```yaml
exclude: ^(\.team/|artifacts/)
```

| Pattern | Content | Reason |
|---------|---------|--------|
| `.team/` | Jules persona code | Separate governance |
| `artifacts/` | Generated output | Not source code |

---

## Recommendations

### Strengths

1. **Layered approach** - External + local hooks provide depth
2. **Auto-fix enabled** - Reduces friction with `--fix --unsafe-fixes`
3. **Strategic ignores** - Documented reasons for each ignored rule
4. **Complexity tracking** - xenon catches what ruff ignores
5. **Project-specific rules** - Custom hooks enforce architecture

### Potential Improvements

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| `--unsafe-fixes` enabled | May auto-change code incorrectly | Review in CI, not pre-commit |
| No mypy in pre-commit | Type errors only in CI | Add mypy hook for faster feedback |
| `check-yaml --unsafe` | Security concern | Remove if not needed for mkdocs |
| Missing `check-executables` | Scripts may lack +x | Add `check-executables-have-shebangs` |

### Hook Execution Time

Expected times (approximate):

| Hook | Time |
|------|------|
| ruff | <1s (incremental) |
| ruff-format | <1s (incremental) |
| standard hooks | <1s each |
| vulture | 2-5s |
| xenon | 2-5s |
| custom scripts | <1s each |
| **Total** | ~10-15s |

---

## Scripts Summary

| Script | Lines | Purpose |
|--------|-------|---------|
| `check_private_imports.py` | 87 | Encapsulation enforcement |
| `check_lint_suppressions.py` | 105 | No inline noqa |
| `check_test_config.py` | 89 | Test fixture usage |
| **Total** | ~281 | |

---

## Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUALITY PIPELINE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LOCAL (pre-commit):     CI (GitHub Actions):                  │
│   ├── ruff ──────────────► ruff (verify)                        │
│   ├── ruff-format ───────► format check                         │
│   ├── vulture ───────────► dead code check                      │
│   └── custom hooks ──────► (no CI equivalent)                   │
│                                                                 │
│   CI-only:                                                      │
│   ├── mypy (type checking)                                      │
│   ├── pytest (full suite)                                       │
│   └── bandit (security scan)                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Conclusion

The pre-commit configuration provides a **comprehensive quality gate** with:

- **14 active hooks** covering linting, formatting, hygiene, and project rules
- **Clear separation** between standard checks and custom enforcement
- **Strategic exclusions** for generated code and separate governance areas
- **Auto-fix capability** to reduce developer friction

The system balances strictness with pragmatism through documented ignores and per-file exceptions.

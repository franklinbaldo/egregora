# Dead Code Detection Guide

**Status**: Phase 3 complete - Manual vulture run recommended

---

## Overview

After removing over-engineered sub-features in Phase 3, additional dead code may remain in the codebase. This guide provides instructions for identifying and removing it.

---

## Phase 3 Summary

**Removed**: 2,141 lines across 24 files

**Deleted**:
- Privacy module (entire directory)
- CLI commands (config, runs)
- Parquet adapter (entire directory)
- Privacy tests
- Privacy configuration classes

---

## Running Vulture

Vulture is a dead code detector for Python. It finds unused classes, functions, variables, and imports.

### Installation

```bash
pip install vulture
```

Or if using uv:
```bash
uv add --dev vulture
```

### Basic Usage

```bash
# Scan entire codebase
vulture src/egregora/

# Scan with minimum confidence (60% = show more potential dead code)
vulture src/egregora/ --min-confidence 60

# Generate report
vulture src/egregora/ --min-confidence 60 > dead_code_report.txt
```

### Expected Dead Code

Based on our removals, vulture will likely find:

#### 1. **Database Schema Fields**

**File**: `src/egregora/database/ir_schema.py`

The `tasks` table may have unused columns related to priority/task management:
- `superseded` status value (was used by ProfileWorker coalescing)

**Action**: Review and potentially remove `superseded` from status enum

#### 2. **DuckDB Manager Methods**

**File**: `src/egregora/database/task_store.py`

- `mark_superseded()` method - used to mark tasks as superseded during profile coalescing

**Action**: Remove if ProfileWorker no longer uses coalescing

#### 3. **Config Validation**

**File**: `src/egregora/config/config_validation.py`

May contain validation functions for removed privacy settings

**Action**: Remove unused privacy validators

#### 4. **Constants**

**File**: `src/egregora/constants.py`

Check for any remaining privacy-related constants we might have missed

**Action**: Verify all privacy constants removed

#### 5. **Imports**

Various files may import removed modules:
- `from egregora.privacy...`
- `from egregora.input_adapters.privacy_config...`

**Action**: Vulture will catch these as import errors

---

## Manual Review Areas

### 1. MkDocs Templates

**Location**: `src/egregora/resources/`

Check if any templates reference privacy features or removed output formats

```bash
grep -r "privacy" src/egregora/resources/
grep -r "parquet" src/egregora/resources/
```

### 2. SQL Queries

**Location**: `src/egregora/resources/sql/`

Check for queries that reference removed tables or columns

```bash
grep -r "privacy" src/egregora/resources/sql/
grep -r "superseded" src/egregora/resources/sql/
```

### 3. Documentation

**Location**: `docs/`, `README.md`

Update any documentation that mentions removed features:
- Privacy/PII features
- CLI commands (config, runs)
- Multiple output formats

### 4. Example Configurations

**Location**: `.egregora/config.yml` examples

Remove privacy configuration examples

---

## Automated Dead Code Detection

### Using Vulture with Whitelist

Create `.vulture_whitelist.py` to mark intentional "dead" code:

```python
# .vulture_whitelist.py
# Intentionally unused - part of public API
from egregora.output_adapters import create_output_sink
from egregora.config import RuntimeContext

# Used dynamically
attr = "dynamic_attribute"
```

Then run:
```bash
vulture src/egregora/ .vulture_whitelist.py
```

### Using Vulture in CI

Add to `.github/workflows/` or pre-commit:

```yaml
- name: Check for dead code
  run: vulture src/egregora/ --min-confidence 80
```

---

## Expected Vulture Findings

### High Confidence (80%+)

- Removed imports still referenced
- Functions that were only called by deleted code
- Classes with no instantiations

### Medium Confidence (60-80%)

- Methods that might be used dynamically
- Public API methods with no internal usage
- Test helper functions

### Low Confidence (<60%)

- Magic methods (`__str__`, `__repr__`)
- Plugin/hook systems (may be called externally)
- Public API (intentionally exported)

---

## Cleanup Checklist

After running vulture:

- [ ] Remove unused imports
- [ ] Remove unused functions
- [ ] Remove unused classes
- [ ] Remove unused constants
- [ ] Update `__all__` exports
- [ ] Remove test code for deleted features
- [ ] Update type hints that reference removed types
- [ ] Clean up docstrings mentioning removed features

---

## Post-Cleanup Validation

### 1. Syntax Check

```bash
python -m py_compile src/egregora/**/*.py
```

### 2. Import Check

```bash
python -c "from egregora.cli import main; print('✓ Imports work')"
```

### 3. Type Check (if using mypy)

```bash
mypy src/egregora/
```

### 4. Run Tests

```bash
pytest tests/ -v
```

---

## Additional Tools

### 1. **Coverage.py**

Find untested code (which may be dead):

```bash
pytest --cov=src/egregora --cov-report=html
# Open htmlcov/index.html to see untested code
```

### 2. **Radon**

Analyze code complexity (unused code often has low complexity):

```bash
radon cc src/egregora/ -a
```

### 3. **Bandit**

Security scanner (may flag removed security features):

```bash
bandit -r src/egregora/
```

---

## Estimated Additional Removals

Based on typical vulture findings after major deletions:

| Category | Estimated Lines |
|----------|----------------|
| Unused imports | ~50 lines |
| Orphaned helpers | ~100 lines |
| Dead config code | ~75 lines |
| Unused DB methods | ~50 lines |
| Test helpers | ~100 lines |
| **Total** | **~375 lines** |

---

## Next Steps

1. **Install vulture** in development environment
2. **Run vulture** with confidence threshold 60%
3. **Review findings** manually (don't auto-delete)
4. **Test after each removal** to ensure nothing breaks
5. **Commit incrementally** with clear messages
6. **Re-run vulture** until minimal findings remain

---

## Example Vulture Output

```
src/egregora/database/task_store.py:142: unused method 'mark_superseded' (60% confidence)
src/egregora/constants.py:87: unused variable 'LEGACY_CONFIG_KEY' (80% confidence)
src/egregora/config/validation.py:45: unused function 'validate_privacy_scope' (90% confidence)
```

---

## Conclusion

Running vulture will help identify the final ~375 lines of dead code remaining after Phase 3 deletions. This is normal and expected after removing large features.

**Recommendation**: Run vulture in a development environment with full dependencies installed, review findings manually, and remove dead code incrementally with testing between removals.

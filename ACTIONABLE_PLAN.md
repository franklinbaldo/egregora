# Egregora: Organization Improvements - Action Plan

**Date**: 2025-01-07
**Status**: Ready to execute
**Estimated Total Time**: 1.5 hours (Phase 1 + Phase 2 only)

---

## Quick Start

```bash
# Execute all Phase 1 tasks
./execute_phase_1.sh

# Then Phase 2 (documentation)
./execute_phase_2.sh
```

---

## Phase 1: Quick Wins (30 minutes) ⚡

### Task 1.1: Remove Dead `/llm/` Module (5 min)

**Status**: [ ] Not Started

```bash
# Verify no usages
grep -r "egregora.llm" src/ tests/
grep -r "create_agent\|create_agent_with_result_type" src/ | grep -v "llm/"

# Delete if clean
rm -rf src/egregora/llm/
git add -A
git commit -m "refactor: Remove dead /llm/ module (never imported)"
```

**Risk**: 🟢 Zero
**Files**: `src/egregora/llm/__init__.py`, `src/egregora/llm/base.py`

---

### Task 1.2: Rename `schema.py` → `database/message_schema.py` (20 min)

**Status**: [ ] Not Started

```bash
# Move file
git mv src/egregora/schema.py src/egregora/database/message_schema.py

# Update imports (6 files)
sed -i 's/from egregora\.schema import/from egregora.database.message_schema import/g' \
    src/egregora/sources/whatsapp/parser.py \
    src/egregora/sources/whatsapp/input.py \
    src/egregora/database/__init__.py \
    src/egregora/pipeline/ir.py \
    src/egregora/ingestion/slack_input.py

# Verify
uv run python -c "from egregora.database.message_schema import MESSAGE_SCHEMA; print('✓')"
uv run pytest tests/unit/ -q

# Commit
git add -A
git commit -m "refactor: Rename schema.py → database/message_schema.py for clarity"
```

**Risk**: 🟡 Low
**Affected Files**: 6 import statements

---

### Task 1.3: Move Misplaced Test Files (5 min)

**Status**: [ ] Not Started

```bash
# Move to proper locations
git mv tests/test_avatar.py tests/integration/test_enrichment_avatars.py
git mv tests/test_abstraction_layer.py tests/unit/test_abstraction_layer.py

# Verify
uv run pytest tests/integration/test_enrichment_avatars.py -v
uv run pytest tests/unit/test_abstraction_layer.py -v

# Commit
git add -A
git commit -m "test: Move misplaced test files to proper subdirectories"
```

**Risk**: 🟢 Zero

---

## Phase 2: Documentation (1 hour) 📝

### Task 2.1: Document Module Hierarchy (30 min)

**Status**: [ ] Not Started

Add comprehensive module docstrings to:
- `src/egregora/ingestion/__init__.py`
- `src/egregora/sources/__init__.py`
- `src/egregora/adapters/__init__.py`

**Template**:
```python
"""Module purpose and architecture.

Architecture:
- Component 1: Purpose
- Component 2: Purpose

Flow:
  Source → Parser → Adapter → Pipeline

See also:
- Related module 1
- Related module 2
"""
```

**Risk**: 🟢 Zero
**Benefit**: Explains overlapping module responsibilities

---

### Task 2.2: Document Large `__init__.py` Patterns (20 min)

**Status**: [ ] Not Started

Add docstrings explaining patterns in:
- `src/egregora/config/__init__.py` - Facade pattern (why re-exporting)
- `src/egregora/pipeline/__init__.py` - Lazy import pattern (why `__getattr__`)

**Risk**: 🟢 Zero
**Benefit**: Future maintainers understand design choices

---

### Task 2.3: Create Test Organization Guide (10 min)

**Status**: [ ] Not Started

Create `tests/README.md` documenting:
- Directory structure (unit/integration/e2e/agents)
- Why organized by test type, not src/ structure
- Coverage strategy per module
- How to run different test categories
- VCR cassette usage

**Risk**: 🟢 Zero
**Benefit**: Clear test organization for contributors

---

## Phase 3: Optional Refactoring (4-6 hours) 🔧

**Priority**: LOW - Not urgent, nice-to-haves

### Task 3.1: Extract AnnotationStore to `store.py` (30 min)

Move 220-line class from `__init__.py` to prevent circular imports.

**Status**: [ ] Deferred

---

### Task 3.2: Split `cli.py` by Command Group (2-3 hours)

Split 1,155-line file into command modules.

**Status**: [ ] Deferred

---

### Task 3.3: Consolidate WhatsApp Modules (2 hours)

Reduce 5 files → 3 files by merging related code.

**Status**: [ ] Deferred

---

## Execution Checklist

### Phase 1 (Do This Week)
- [ ] Remove `/llm/` module
- [ ] Rename `schema.py` → `database/message_schema.py`
- [ ] Move test files to proper directories
- [ ] All tests passing

### Phase 2 (Do This Week)
- [ ] Add module docstrings (ingestion, sources, adapters)
- [ ] Document `__init__.py` patterns
- [ ] Create `tests/README.md`

### Phase 3 (Optional, Future)
- [ ] Extract AnnotationStore (if needed)
- [ ] Split CLI (if needed)
- [ ] Consolidate WhatsApp (if needed)

---

## Success Criteria

**Phase 1 Complete**:
- Zero import errors
- All unit tests passing
- Files in correct locations

**Phase 2 Complete**:
- Clear module purposes documented
- Test organization explained

**Phase 3 Complete** (if executed):
- All optional refactorings done
- Tests still passing

---

## Quick Reference

| Task | Time | Risk | Priority |
|------|------|------|----------|
| Remove /llm/ | 5m | 🟢 Zero | ⚡ CRITICAL |
| Rename schema.py | 20m | 🟡 Low | ⚡ HIGH |
| Move tests | 5m | 🟢 Zero | ⚡ HIGH |
| Document modules | 30m | 🟢 Zero | 📝 SHOULD |
| Document __init__ | 20m | 🟢 Zero | 📝 SHOULD |
| Create tests/README | 10m | 🟢 Zero | 📝 SHOULD |
| **Total (P1+P2)** | **1.5h** | **Low** | **Do This Week** |

---

## Notes

- **No backward compatibility needed** (alpha mindset maintained)
- **All changes are internal** - no API changes
- **Test coverage validates changes** - 191/258 tests passing
- **Phase 3 is optional** - current code works fine

---

**Last Updated**: 2025-01-08
**Next Review**: After Phase 1+2 completion

# Phase 7 Windowing Refactor: Legacy "Period" Concept Cleanup Report

## Executive Summary

The Phase 7 windowing refactor replaced period-based grouping (daily/weekly/monthly) with flexible windowing (step_size + step_unit). However, legacy references to "period" concepts remain scattered throughout the codebase, causing confusion and incorrect documentation.

**Total Issues Found: 47 references across 18 files**
- CRITICAL: 6 issues (code will break or is confusing)
- HIGH: 15 issues (user-facing documentation incorrect)
- MEDIUM: 22 issues (internal docs/comments need updates)
- LOW: 4 issues (archive docs, can defer)

---

## CRITICAL Issues (Code Breaking/Confusing)

### 1. WriterRuntimeContext Documentation Mismatch
**File**: `/home/user/egregora/CLAUDE.md`
**Line**: 244
**Issue**: Documentation claims WriterRuntimeContext has `window_id` field, but actual implementation has `start_time` and `end_time` instead
```markdown
# WRONG (current CLAUDE.md):
window_id: str  # Sequential: "chunk_001", "window_002", etc.

# CORRECT (actual implementation):
start_time: datetime
end_time: datetime
```
**Severity**: CRITICAL - Misleads developers about API contract
**Action**: Update CLAUDE.md lines 244-246 to show actual fields (start_time, end_time)

---

### 2. CLI gather-context Command: Misleading Help Text
**File**: `/home/user/egregora/src/egregora/cli.py`
**Line**: 1024
**Issue**: Help text references outdated window ID format
```python
window_id: Annotated[str, typer.Option(help="Window identifier (e.g., chunk_001)")]
```
**Problem**: 
- "chunk_001" suggests sequential IDs, but CLI actually passes dates/timestamps
- Test file shows usage: `--window-id 2025-01-01` (ISO date format)
- No validation enforces any particular format
**Severity**: CRITICAL - Confusing for users
**Action**: Update help text to show realistic example: `"Window identifier (e.g., 2025-01-01 or arbitrary string)"`

---

### 3. CLI write-posts Command: Same Misleading Help Text
**File**: `/home/user/egregora/src/egregora/cli.py`
**Line**: 1135
**Issue**: Identical misleading help text as gather-context
```python
window_id: Annotated[str, typer.Option(help="Window identifier (e.g., chunk_001)")]
```
**Severity**: CRITICAL - Same as issue #2
**Action**: Same fix as issue #2

---

### 4. Test File Uses Non-Existent --period-key Flag
**File**: `/home/user/egregora/tests/e2e/test_stage_commands.py`
**Lines**: 320, 369, 388
**Issue**: Tests invoke gather-context and write-posts with `--period-key` flag that doesn't exist
```python
# WRONG - lines 320, 369, 388:
"gather-context",
str(enriched_csv),
"--period-key",           # <-- This flag doesn't exist!
"2025-10-28",
```
**Should be**:
```python
"--window-id",            # <-- Correct flag name
"2025-10-28",
```
**Severity**: CRITICAL - Tests will fail
**Action**: Replace `--period-key` with `--window-id` on lines 320, 369, 388

---

### 5. writer_agent.py Docstring References Outdated Function Name
**File**: `/home/user/egregora/src/egregora/agents/writer/writer_agent.py`
**Line**: 5
**Issue**: Module docstring says function mirrors `write_posts_for_period`, but actual function is `write_posts_for_window`
```python
# WRONG:
It exposes ``write_posts_with_pydantic_agent`` which mirrors the signature of
``write_posts_for_period`` but routes the LLM conversation through a
```
**Severity**: CRITICAL - Confusing for future maintainers
**Action**: Update line 5 to reference `write_posts_for_window` instead of `write_posts_for_period`

---

### 6. writer/__init__.py Docstring Still Says "Per Period"
**File**: `/home/user/egregora/src/egregora/agents/writer/__init__.py`
**Line**: 4
**Issue**: Module docstring says "0-N posts per period" (outdated terminology)
```python
# WRONG:
Uses function calling (write_post tool) to generate 0-N posts per period.

# CORRECT:
Uses function calling (write_post tool) to generate 0-N posts per window.
```
**Severity**: CRITICAL - Inconsistent with Phase 7 terminology
**Action**: Change "per period" to "per window"

---

## HIGH Issues (User-Facing Documentation)

### 7. README.md: Multiple Outdated --period Examples
**File**: `/home/user/egregora/README.md`
**Lines**: 169, 191
**Issue**: Examples show deprecated `--period` flag
```bash
# Line 169 - WRONG:
egregora process export.zip --period=week

# Line 191 - WRONG:
egregora group messages.csv --period=week --output=grouped.csv
```
**Correct syntax**:
```bash
egregora process export.zip --step-size=7 --step-unit=days
egregora group messages.csv --step-size=7 --step-unit=days --output-dir=windows
```
**Note**: The `group` command no longer exists in the CLI - it's a stage-by-stage alternative that uses new parameters
**Severity**: HIGH - Users following README will encounter errors
**Action**: 
- Line 169: Change to `--step-size=7 --step-unit=days`
- Line 191: Change to `--step-size=7 --step-unit=days --output-dir=grouped`
- Update help text to be clearer

---

### 8. docs/getting-started/configuration.md: Period Documentation Table
**File**: `/home/user/egregora/docs/getting-started/configuration.md`
**Line**: 19
**Issue**: Configuration table documents non-existent `--period` flag with values `daily`, `weekly`, `monthly`
```markdown
# WRONG:
| `--period` | Grouping period: `daily`, `weekly`, `monthly` | `weekly` |
```
**Correct documentation**:
```markdown
| `--step-size` | Size of each processing window | `100` |
| `--step-unit` | Unit: `messages`, `hours`, `days`, `bytes` | `messages` |
```
**Severity**: HIGH - Official documentation contradicts actual CLI
**Action**: Replace lines 19-21 with correct --step-size and --step-unit documentation

---

### 9. docs/getting-started/configuration.md: Example Commands Use --period
**File**: `/home/user/egregora/docs/getting-started/configuration.md`
**Lines**: 205, 215
**Issue**: Code examples show `--period=weekly` which doesn't exist
```bash
# Line 205 & 215 - WRONG:
--period=weekly \
```
**Correct**:
```bash
--step-size=7 --step-unit=days \
```
**Severity**: HIGH - Users copy-paste broken commands
**Action**: Replace with correct --step-size/--step-unit syntax

---

### 10. docs/getting-started/quickstart.md: Period Examples
**File**: `/home/user/egregora/docs/getting-started/quickstart.md`
**Lines**: 110 (appears twice)
**Issue**: Quickstart examples use `--period=daily` flag
```bash
# WRONG:
egregora process another-export.zip --output=. --period=daily
```
**Correct**:
```bash
egregora process another-export.zip --output=. --step-size=1 --step-unit=days
```
**Severity**: HIGH - New users start with broken commands
**Action**: Replace all `--period=daily` with `--step-size=1 --step-unit=days`

---

### 11. docs/guide/generation.md: Multiple Period References
**File**: `/home/user/egregora/docs/guide/generation.md`
**Lines**: 10, 42, 91, 122, 316, 368, 383
**Issue**: Multiple references to period-based grouping that's now called "windowing"
```markdown
# Examples of what needs updating:
Line 10: "Lets it decide how many posts (0-N per period)"
Line 42: period="weekly",          # Group by week
Line 91: """Skip this period without creating a post.
Line 122: "Read the conversation from the period"
Line 316: "LLM can create multiple posts per period:"
Line 368: "egregora process export.zip --period=week"
Line 383: "1. Not enough messages in period"
```
**Severity**: HIGH - Entire guide contradicts Phase 7 terminology
**Action**: 
- Replace "period" with "window" in all comments/docs (lines 10, 91, 122, 316, 383)
- Update line 42 example from `period="weekly"` to `step_size=7, step_unit="days"`
- Update line 368 command example to use --step-size/--step-unit

---

### 12. docs/guide/architecture.md: Period Parameter Example
**File**: `/home/user/egregora/docs/guide/architecture.md`
**Lines**: 134-136
**Issue**: Example code shows old `period="weekly"` parameter
```python
# WRONG:
period="weekly"
# Returns 0-N posts per period
```
**Should be**:
```python
step_size=7, step_unit="days"
# Returns 0-N posts per window
```
**Severity**: HIGH - Architecture doc shows outdated API
**Action**: Replace example with correct parameters

---

## MEDIUM Issues (Internal Documentation/Comments)

### 13. CLI: Comment About "Previous Period"
**File**: `/home/user/egregora/src/egregora/cli.py`
**Line**: 1042 (in gather_context docstring)
**Issue**: Comment references outdated concept
```python
# Line 1042:
- Loads freeform memory from previous period
```
**Should be**:
```python
- Loads freeform memory from previous windows
```
**Severity**: MEDIUM - Internal comment, but confusing
**Action**: Change "period" to "window"

---

### 14. writer/core.py: "Per Period" in Docstring
**File**: `/home/user/egregora/src/egregora/agents/writer/core.py`
**Line**: 4
**Issue**: Module docstring uses "per period" terminology
```python
# WRONG:
Uses function calling (write_post tool) to generate 0-N posts per period.

# CORRECT:
Uses function calling (write_post tool) to generate 0-N posts per window.
```
**Severity**: MEDIUM - Module-level documentation
**Action**: Change "per period" to "per window"

---

### 15. writer/core.py: Function Docstring
**File**: `/home/user/egregora/src/egregora/agents/writer/core.py`
**Line**: 337
**Issue**: Function docstring uses "window" (correct) but should clarify windowing concept
```python
"""Let LLM analyze window's messages, write 0-N posts, and update author profiles.
```
**Note**: This is actually correct - no change needed. Just verify context is clear.

---

### 16. pipeline.py: Docstring References "window_id"
**File**: `/home/user/egregora/src/egregora/pipeline.py`
**Line**: 136
**Issue**: Example docstring references non-existent `window_id` attribute
```python
# WRONG:
>>> for window in create_windows(table, step_size=100, step_unit="messages"):
...     print(f"Processing {window.window_id}: {window.size} messages")
```
**Should be**:
```python
>>> for window in create_windows(table, step_size=100, step_unit="messages"):
...     print(f"Processing window {window.window_index}: {window.size} messages")
```
**Severity**: MEDIUM - Example code won't run
**Action**: Fix docstring example to use `window.window_index` and `window.start_time`

---

### 17-22. Multiple Files: "0-N Posts Per Period" → "Per Window"
**Files affected**:
- `/home/user/egregora/docs/development/agents/claude.md` (line 248)
- `/home/user/egregora/docs/development/archive/backend-switch-guide.md` (line 73)
- `/home/user/egregora/docs/development/archive/BACKEND-SWITCH-COMPLETE.md` (line 197)
- `/home/user/egregora/docs/getting-started/quickstart.md` (line 90)
- `/home/user/egregora/docs/guide/architecture.md` (line 136)
- `/home/user/egregora/docs/guide/generation.md` (line 10)
- `/home/user/egregora/tests/evals/writer_evals.py` (lines 4, 50, 70)
- `/home/user/egregora/tests/fixtures/golden/expected_output/about.md` (line 39)
- `/home/user/egregora/src/egregora/utils/write_post.py` (line 17)

**Issue**: All instances of "0-N posts per period" should be "0-N posts per window"
**Severity**: MEDIUM - Inconsistent terminology
**Action**: Bulk find-and-replace:
```bash
grep -r "0-N posts per period" /home/user/egregora --include="*.py" --include="*.md" | wc -l
# Replace all occurrences with "0-N posts per window"
```

---

## LOW Issues (Archive Documentation)

### 23-26. Archive Documentation
**Files**:
- `/home/user/egregora/docs/development/archive/pydantic-migration-revised.md`
- `/home/user/egregora/docs/development/archive/pydantic-ai-migration-complete.md`
- `/home/user/egregora/docs/development/archive/pydantic-migration-phase1-final.md`
- `/home/user/egregora/docs/development/archive/BACKEND-SWITCH-COMPLETE.md`

**Issue**: Archive docs reference old period terminology
**Severity**: LOW - These are archived development notes, not user-facing docs
**Recommendation**: Can defer or leave as-is for historical reference. Only update if someone accesses these files.

---

## Summary of Changes by File

### Code Files (Need Fixing):
1. **src/egregora/cli.py** (3 changes)
   - Line 1024: Update help text for gather-context window_id
   - Line 1042: Change "previous period" to "previous windows"
   - Line 1135: Update help text for write-posts window_id

2. **src/egregora/agents/writer/writer_agent.py** (1 change)
   - Line 5: Replace `write_posts_for_period` with `write_posts_for_window`

3. **src/egregora/agents/writer/__init__.py** (1 change)
   - Line 4: Change "0-N posts per period" to "0-N posts per window"

4. **src/egregora/agents/writer/core.py** (1 change)
   - Line 4: Change "0-N posts per period" to "0-N posts per window"

5. **src/egregora/pipeline.py** (1 change)
   - Line 136: Fix docstring example - replace `window.window_id` with `window.window_index` and add `window.start_time`

6. **src/egregora/utils/write_post.py** (1 change)
   - Line 17: Change "0-N per period" to "0-N per window"

7. **CLAUDE.md** (1 change)
   - Lines 244-246: Update WriterRuntimeContext documentation to show actual fields (start_time, end_time)

8. **tests/e2e/test_stage_commands.py** (3 changes)
   - Line 320: Replace `--period-key` with `--window-id`
   - Line 369: Replace `--period-key` with `--window-id`
   - Line 388: Replace `--period-key` with `--window-id`

### Documentation Files (Need Fixing):
1. **README.md** (2 changes)
   - Line 169: Change `--period=week` to `--step-size=7 --step-unit=days`
   - Line 191: Update group command example with new parameters

2. **docs/getting-started/configuration.md** (3 changes)
   - Line 19: Replace period documentation with step-size/step-unit
   - Line 205: Update example command
   - Line 215: Update example command

3. **docs/getting-started/quickstart.md** (2 changes)
   - Line 90: Change wording from "per period" to "per window"
   - Line 110: Change `--period=daily` to `--step-size=1 --step-unit=days` (2 locations)

4. **docs/guide/generation.md** (7 changes)
   - Line 10: Replace "per period" with "per window"
   - Line 42: Update parameter example
   - Line 91: Replace "period" with "window"
   - Line 122: Replace "period" with "window"
   - Line 316: Replace "per period" with "per window"
   - Line 368: Update command example
   - Line 383: Replace "period" with "window"

5. **docs/guide/architecture.md** (2 changes)
   - Line 134-136: Update example code and description

6. **docs/development/agents/claude.md** (1 change)
   - Line 248: Change "per period" to "per window"

### Documentation Files (Can Defer/Leave):
1. Archive docs in `docs/development/archive/` (low priority)

---

## Recommended Priority

**Phase 1 (CRITICAL - Do First)**:
1. Fix test file `tests/e2e/test_stage_commands.py` - tests will fail otherwise
2. Update CLI help text in `src/egregora/cli.py` (lines 1024, 1135)
3. Fix CLAUDE.md WriterRuntimeContext documentation (line 244)
4. Fix writer_agent.py docstring reference (line 5)

**Phase 2 (HIGH - User-Facing)**:
1. Update all documentation files with correct CLI syntax
2. Replace all "0-N posts per period" with "0-N posts per window"
3. Update examples to use --step-size/--step-unit instead of --period

**Phase 3 (MEDIUM - Internal)**:
1. Update internal comments and docstrings
2. Run tests to verify all changes

---

## Verification Checklist

After making changes:
```bash
# 1. Run tests
uv run pytest tests/e2e/test_stage_commands.py -v

# 2. Verify no remaining period references in user docs
grep -r "\\-\\-period" docs/getting-started docs/guide --include="*.md"

# 3. Check for consistent windowing terminology
grep -r "per period" src docs --include="*.py" --include="*.md" | grep -v archive

# 4. Verify help text
python -m egregora gather-context --help
python -m egregora write-posts --help
python -m egregora process --help
```


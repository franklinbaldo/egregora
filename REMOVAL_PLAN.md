# Egregora Sub-Feature Removal Plan

**Goal**: Remove over-engineered sub-features to simplify codebase while maintaining core functionality.

**Strategy**: Phased approach - disconnect, test, then delete.

---

## Phase 1: Disconnect & Stub Out

Disable features without deleting code, allowing rollback if issues arise.

### 1.1 Privacy Module Disconnection

**Impact**: Remove entire PII detection and privacy system

#### Files to Modify:

**`src/egregora/input_adapters/whatsapp/adapter.py`**
- Lines 58-62: Comment out privacy config initialization
- Lines 115-150: Comment out `_apply_privacy()` method calls
- Stub: Return table unchanged

**`src/egregora/input_adapters/whatsapp/parsing.py`**
- Line 174: Replace `deterministic_author_uuid()` with simple UUID generation
- Line 313: Comment out `anonymize_table()` call

**`src/egregora/agents/writer.py`**
- Lines 209-219: Set `pii_prevention = None` (skip building PII context)

**`src/egregora/agents/enricher.py`**
- Line 175: Set `pii_prevention: dict[str, Any] | None = None` as default
- Line 663-672 in `write_pipeline.py`: Set `pii_prevention = None`

**`src/egregora/prompts/enrichment.jinja`**
- Lines 1-2: Comment out privacy macro import and call

**`src/egregora/prompts/writer.jinja`**
- Lines 28-29: Comment out privacy macro import and call

---

### 1.2 CLI Commands Disconnection

**Impact**: Remove `egregora config` and `egregora runs` commands

#### Files to Modify:

**`src/egregora/cli/main.py`**
- Line 26: Comment out `from egregora.cli.config import config_app`
- Line 28: Keep `get_storage` but comment out `runs_app` import
- Line 44: Comment out `app.add_typer(config_app)`
- Line 45: Comment out `app.add_typer(runs_app)`

**Dependency Issue**: `get_storage()` used by:
- Line 473: `top()` command
- Line 554: `show_reader_history()` command

**Solution**: Move `_RunsDuckDBStorage` and `get_storage()` to `src/egregora/database/task_store.py`

---

### 1.3 Parquet Output Adapter Disconnection

**Impact**: Remove parquet/JSON export capability

#### Files to Modify:

**`src/egregora/output_adapters/__init__.py`**
- Remove parquet adapter from exports

**Check for Usage**:
```bash
grep -r "parquet" src/egregora/
grep -r "ParquetAdapter" src/egregora/
```

If not actively used in pipeline, can skip straight to deletion.

---

### 1.4 Task System Priority Disconnection

**Impact**: Remove priority-based scheduling, keep simple FIFO queue

#### Current Priority Order:
1. BannerWorker (highest)
2. ProfileWorker (medium, with coalescing)
3. EnrichmentWorker (lowest)

#### Files to Modify:

**`src/egregora/orchestration/write_pipeline.py`** (lines 210-238)
- Modify `_process_background_tasks()` to run workers in **parallel** or **single combined queue**
- Remove sequential execution (priority ordering)

**`src/egregora/agents/profile/worker.py`**
- Lines with coalescing logic: Comment out task deduplication
- Change to simple FIFO processing (like other workers)
- Remove `mark_superseded()` calls

**Alternative**: Keep all three workers but document that execution order is not guaranteed

---

### 1.5 Rate Limiting Simplification

**Impact**: Remove concurrent and daily limits, keep only per-second

#### Files to Modify:

**`src/egregora/config/settings.py`**
- Search for rate limiting config fields (concurrent, daily)
- Comment out or set to None

**Check for Usage**:
```bash
grep -r "concurrent.*limit" src/egregora/
grep -r "daily.*limit" src/egregora/
```

---

## Phase 2: Testing

Run e2e tests to verify core functionality remains intact.

### 2.1 Run Existing E2E Tests

```bash
pytest tests/e2e/ -v
```

**Expected Results**:
- Privacy tests should FAIL (expected - we disabled privacy)
- CLI tests for `config` and `runs` should FAIL (expected)
- All other pipeline tests should PASS

### 2.2 Manual Testing

**Test Write Pipeline**:
```bash
egregora write --max-windows 2
```

**Verify**:
- ✅ Messages ingested without privacy
- ✅ Enrichment runs
- ✅ Posts generated
- ✅ MkDocs output created

**Test CLI**:
```bash
egregora --help  # Should NOT show 'config' or 'runs' commands
egregora read    # Should still work
egregora init    # Should still work
```

---

## Phase 3: Delete Code

After tests pass, permanently remove disconnected code.

### 3.1 Privacy Module Deletion

**Delete Directories**:
```bash
rm -rf src/egregora/privacy/
```

**Delete Files**:
```bash
rm src/egregora/input_adapters/privacy_config.py
rm src/egregora/prompts/_privacy_macros.jinja
rm tests/unit/privacy/test_privacy_config.py
```

**Clean Imports**: Remove all commented import statements from Phase 1

**Update Config**:
- `src/egregora/config/settings.py`: Remove `PrivacySettings`, `PIIPreventionSettings`, `StructuralPrivacySettings`, `AgentPIISettings` classes
- Remove `privacy` field from global config (line 756)

**Update Constants**:
- `src/egregora/constants.py`: Remove `AuthorPrivacyStrategy`, `MentionPrivacyStrategy`, `TextPIIStrategy`, `PIIScope`, `PrivacyMarkers` enums (lines 149-204)

---

### 3.2 CLI Commands Deletion

**Delete Files**:
```bash
rm src/egregora/cli/config.py
rm src/egregora/cli/runs.py
rm tests/e2e/cli/test_runs_command.py
```

**Refactor `get_storage()`**:
- Move to `src/egregora/database/task_store.py`
- Update imports in `cli/main.py`

**Clean Imports**: Remove commented imports from `cli/main.py` and `cli/__init__.py`

---

### 3.3 Parquet Adapter Deletion

**Delete Directory**:
```bash
rm -rf src/egregora/output_adapters/parquet/
```

**Update Exports**:
- `src/egregora/output_adapters/__init__.py`: Remove parquet references

---

### 3.4 Task Priority Deletion

**Modify Files**:
- `src/egregora/orchestration/write_pipeline.py`: Simplify `_process_background_tasks()` to single loop
- `src/egregora/agents/profile/worker.py`: Remove coalescing logic
- `src/egregora/database/task_store.py`: Remove `mark_superseded()` method

**Database Schema**:
- Consider: Remove `superseded` status from `tasks` table schema?
  - Keep for now (no harm, used for historical tracking)

---

### 3.5 Rate Limiting Deletion

**Modify Files**:
- `src/egregora/config/settings.py`: Remove concurrent and daily limit fields from rate limiting config
- Search and remove any enforcement logic for concurrent/daily limits

---

## Phase 4: Documentation Update

### 4.1 Update FEATURES.md

Already done in previous commit, but verify:
- ✅ Privacy section removed
- ✅ Search simplified to semantic-only
- ✅ Output simplified to MkDocs-only
- ✅ Configuration override simplified
- ✅ Rate limiting simplified to per-second

**Additional Updates Needed**:
- Remove `egregora config` from CLI commands section (line ~388)
- Remove `egregora runs` from CLI commands section (line ~389)

### 4.2 Update README.md

Check if README mentions:
- Privacy/PII features
- CLI commands (`config`, `runs`)
- Multiple output formats

Update or remove these sections.

### 4.3 Update CHANGELOG.md

Add entry:
```markdown
## [Unreleased] - Simplification Release

### Removed
- **Privacy Module**: Removed entire PII detection and privacy system
- **CLI Commands**: Removed `egregora config` and `egregora runs` commands
- **Output Formats**: Removed parquet/JSON export, MkDocs only
- **Task Priorities**: Simplified to FIFO queue, removed priority scheduling
- **Rate Limiting**: Removed concurrent and daily limits, per-second only
- **Search Modes**: Removed keyword/hybrid search, semantic-only

### Rationale
Removed over-engineered sub-features to reduce complexity while maintaining core functionality.
```

---

## Phase 5: Git Commit Strategy

### Commit 1: Disconnect (Phase 1)
```bash
git add -A
git commit -m "refactor: disconnect privacy, CLI commands, and task priorities

- Stub out privacy module calls
- Disable config and runs CLI commands
- Comment out task priority logic
- Prepare for feature removal after testing"
```

### Commit 2: Test Results (Phase 2)
```bash
git commit -m "test: verify e2e tests pass with features disabled

- Document test results
- Confirm core pipeline functionality intact"
```

### Commit 3: Delete Code (Phase 3)
```bash
git add -A
git commit -m "refactor: remove privacy, CLI commands, parquet adapter, task priorities

BREAKING CHANGE: Remove over-engineered sub-features

Removed:
- Privacy module (PII detection/anonymization)
- CLI commands (config, runs)
- Parquet output adapter
- Task priority scheduling
- Concurrent/daily rate limits

All core functionality (write pipeline, enrichment, MkDocs output) verified working."
```

### Commit 4: Documentation (Phase 4)
```bash
git add FEATURES.md README.md CHANGELOG.md
git commit -m "docs: update documentation after feature removal

- Update FEATURES.md
- Update README.md
- Add CHANGELOG.md entry"
```

---

## Rollback Plan

If Phase 2 testing reveals issues:

1. **Revert Phase 1 changes**:
   ```bash
   git revert HEAD  # Revert disconnect commit
   ```

2. **Identify specific failing tests**
3. **Keep only necessary features**
4. **Create refined removal plan**

---

## Risk Assessment

| Feature | Risk Level | Mitigation |
|---------|-----------|------------|
| Privacy Module | 🟢 Low | Only used in WhatsApp adapter, easy to verify |
| CLI Commands | 🟢 Low | Standalone commands, no pipeline deps |
| Parquet Adapter | 🟢 Low | Likely unused, verify with grep first |
| Task Priorities | 🟡 Medium | Core to pipeline, test thoroughly |
| Rate Limiting | 🟢 Low | Config-only change |

---

## Estimated Impact

**Code Deletion**:
- ~1,000+ lines of Python removed
- ~500+ lines of tests removed
- ~50+ lines of documentation removed

**Maintenance Reduction**:
- 3 fewer modules to maintain
- 2 fewer CLI commands to support
- 1 fewer output format to test
- Simplified config surface area

**Performance**:
- Neutral to slight improvement (less code to execute)
- Task processing may be slightly faster (no priority overhead)

---

## Next Steps

1. Review this plan
2. Execute Phase 1 (disconnect)
3. Run Phase 2 (testing)
4. If tests pass → Execute Phase 3 (delete)
5. Update documentation (Phase 4)
6. Commit and push (Phase 5)

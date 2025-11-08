# Week 1 Execution Guide

**Goal**: Green-to-green foundation with IR v1, privacy capability, and lineage tracking.

**Timeline**: 5 days (2025-01-08 to 2025-01-13)

---

## Daily Breakdown

### Day 1 (Monday): Schema Foundation
**Duration**: ~2 hours

#### Tasks
1. **QW-0: IR v1 Lockfile** (30 min)
   - [ ] Create `schema/ir_v1.sql`
   - [ ] Create `schema/ir_v1.json` (Ibis schema dump)
   - [ ] Create `scripts/check_ir_schema.py`
   - [ ] Update `.github/workflows/ci.yml`
   - [ ] Test: `uv run python scripts/check_ir_schema.py`

2. **QW-1: Pandas CI Enforcement** (5 min)
   - [ ] Update `.github/workflows/ci.yml`
   - [ ] Add: `uv run python tests/linting/test_no_pandas_escape.py`
   - [ ] Test: Verify CI fails on pandas import

3. **QW-4: UUID5 Namespaces** (20 min)
   - [ ] Create `src/egregora/privacy/constants.py`
   - [ ] Update `src/egregora/privacy/anonymizer.py`
   - [ ] Create `docs/architecture/adr-002-deterministic-uuids.md`
   - [ ] Test: `from egregora.privacy.constants import NS_AUTHORS`

**Acceptance**:
- [ ] CI fails on IR schema drift
- [ ] CI fails on pandas imports
- [ ] Re-ingest produces identical UUIDs

---

### Day 2 (Tuesday): Privacy Capability
**Duration**: ~2.5 hours

#### Tasks
1. **QW-3: PrivacyPass Capability Token** (45 min)
   - [ ] Create `src/egregora/privacy/gate.py`
   - [ ] Implement `PrivacyPass` NamedTuple
   - [ ] Implement `@require_privacy_pass` decorator
   - [ ] Implement `PrivacyGate.run()` method
   - [ ] Test: `tests/unit/test_privacy_pass.py`

2. **Update Privacy Config** (30 min)
   - [ ] Add `tenant_id` to `PrivacyConfig`
   - [ ] Update anonymizer to use namespaced UUIDs
   - [ ] Test: Multi-tenant isolation

3. **ADR Documentation** (30 min)
   - [ ] Create `docs/architecture/adr-002-privacy-gate.md`
   - [ ] Document re-identification escrow policy
   - [ ] Document capability token rationale

**Acceptance**:
- [ ] `@require_privacy_pass` decorator works
- [ ] Runtime error without privacy_pass kwarg
- [ ] Property test: 0% LLM calls without PrivacyPass

---

### Day 3 (Wednesday): Runs & Lineage
**Duration**: ~3 hours

#### Tasks
1. **Runs Table Schema** (30 min)
   - [ ] Create `schema/runs_v1.sql`
   - [ ] Create `schema/lineage_v1.sql`
   - [ ] Add migration script: `scripts/create_runs_tables.py`
   - [ ] Test: DuckDB table creation

2. **Runs Tracking Implementation** (1.5 hours)
   - [ ] Create `src/egregora/pipeline/runner.py`
   - [ ] Implement `run_stage_with_tracking()`
   - [ ] Implement `record_run()`
   - [ ] Test: `tests/unit/test_runs_tracking.py`

3. **Runs CLI Commands** (1 hour)
   - [ ] Create `src/egregora/cli/runs.py`
   - [ ] Implement `egregora runs tail`
   - [ ] Implement `egregora runs show <run_id>`
   - [ ] Implement `egregora runs lineage <run_id>`
   - [ ] Test: Manual CLI testing

**Acceptance**:
- [ ] Every stage writes to runs table
- [ ] `egregora runs tail` shows last 10 runs
- [ ] `egregora runs show <run_id>` shows details

---

### Day 4 (Thursday): Observability & Checkpoints
**Duration**: ~3 hours

#### Tasks
1. **QW-5: OpenTelemetry Bootstrap** (30 min)
   - [ ] Create `src/egregora/utils/telemetry.py`
   - [ ] Implement `configure_otel()`
   - [ ] Test: `EGREGORA_OTEL=1 egregora pipeline run`

2. **Content-Addressed Checkpoints** (2 hours)
   - [ ] Create `src/egregora/pipeline/checkpoint.py`
   - [ ] Implement `fingerprint_stage_input()`
   - [ ] Implement `checkpoint_path()`
   - [ ] Implement `load_checkpoint()` / `save_checkpoint()`
   - [ ] Test: `tests/unit/test_checkpoint_fingerprint.py`

3. **QW-2: Slack Adapter Fail-Fast** (10 min)
   - [ ] Update `src/egregora/ingestion/slack_input.py`
   - [ ] Add `raise NotImplementedError` for stub
   - [ ] Test: Verify error on Slack export

**Acceptance**:
- [ ] Traces emitted when `EGREGORA_OTEL=1`
- [ ] Same input → same fingerprint (deterministic)
- [ ] Slack adapter raises NotImplementedError

---

### Day 5 (Friday): Golden Test & Doctor
**Duration**: ~3 hours

#### Tasks
1. **Golden WhatsApp Test** (2 hours)
   - [ ] Create `tests/e2e/test_week1_golden.py`
   - [ ] Test: WhatsApp ZIP → IR v1 → privacy → chunks
   - [ ] Verify: No LLM calls, just structural pipeline
   - [ ] Target: <5 min end-to-end

2. **Doctor Command** (1 hour)
   - [ ] Create `src/egregora/cli/doctor.py`
   - [ ] Implement environment checks
   - [ ] Implement adapter discovery check
   - [ ] Implement IR schema validation check
   - [ ] Test: `egregora doctor`

**Acceptance**:
- [ ] Golden test passes (<5 min)
- [ ] Property test: re-ingest → identical event_id
- [ ] `egregora doctor` validates environment

---

## Week 1 Checklist (Master)

### Quick Wins
- [ ] QW-0: IR v1 lockfile + CI check
- [ ] QW-1: Pandas CI enforcement
- [ ] QW-2: Slack adapter fail-fast
- [ ] QW-3: PrivacyPass capability token
- [ ] QW-4: UUID5 namespaces
- [ ] QW-5: OpenTelemetry bootstrap

### Infrastructure
- [ ] Runs + lineage tables created
- [ ] Runs tracking in all stages
- [ ] Content-addressed checkpoints
- [ ] CLI commands: `runs tail`, `runs show`, `doctor`

### Testing
- [ ] Golden WhatsApp test (<5 min)
- [ ] Property test: UUID determinism
- [ ] Property test: re-ingest stability
- [ ] CI schema drift detection

### Documentation
- [ ] ADR-002: Deterministic UUIDs
- [ ] ADR-002: Privacy gate capability token
- [ ] `docs/architecture/ir-v1-spec.md`

---

## Success Criteria

### Must Have (P0)
- ✅ CI fails on IR schema drift
- ✅ CI fails on pandas imports
- ✅ `egregora runs tail` functional
- ✅ Privacy gate enforced via capability token
- ✅ Re-ingest produces identical UUIDs

### Should Have (P1)
- ✅ Golden test completes in <5 min
- ✅ OpenTelemetry traces (opt-in)
- ✅ Doctor command validates environment
- ✅ Checkpoints are deterministic

### Nice to Have (P2)
- ⭕ Cache GC command
- ⭕ Adapter plugin loader
- ⭕ View registry

---

## Troubleshooting

### Issue: CI schema check fails
**Solution**: Run `uv run python scripts/check_ir_schema.py --update` to regenerate lockfile

### Issue: PrivacyPass decorator not working
**Solution**: Ensure all LLM functions have `privacy_pass: PrivacyPass` as kwarg-only param

### Issue: Runs table not created
**Solution**: Run `uv run python scripts/create_runs_tables.py` manually

### Issue: Golden test timeout
**Solution**: Disable enrichment, focus on structural pipeline only

---

## Daily Standup Template

**Yesterday**: [What was completed]
**Today**: [What will be worked on]
**Blockers**: [Any blockers or questions]
**Tests Passing**: [Number of tests passing]

---

## End of Week 1 Review

**Date**: 2025-01-13 (Friday EOD)

### Review Checklist
- [ ] All P0 success criteria met
- [ ] All tests passing
- [ ] CI green
- [ ] Golden test <5 min
- [ ] Documentation complete

### Demo
- Show: `egregora doctor` output
- Show: `egregora runs tail`
- Show: Golden test run
- Show: CI failing on pandas import
- Show: Re-ingest producing identical UUIDs

### Retrospective Questions
1. What went well?
2. What could be improved?
3. Any architectural concerns discovered?
4. Ready for Week 2 (Adapter plugins)?

---

**Created**: 2025-01-08
**Status**: Ready for execution
**Team Size**: 1-2 developers
**Estimated Effort**: 13-15 hours total

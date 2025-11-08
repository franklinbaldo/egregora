# Architecture Roadmap - Executive Summary

**Date**: 2025-01-08
**Status**: Planning Complete → Ready for Implementation
**Branch**: `claude/actionable-plan-011CUur116K7c4WxATK5d2y4`

---

## What We Built

### 1. **ARCHITECTURE_ROADMAP.md** (1,320 lines)
Comprehensive 90-day architecture roadmap with:

**North-Star Architecture** (6 layers):
- Layer 0: Tenant Boundary (multi-tenant ready)
- Layer 1: Sources → Adapters → IR v1 (versioned, locked)
- Layer 2: Privacy Boundary (capability-based)
- Layer 3: Processing Pipeline (content-addressed checkpoints)
- Layer 4: Agents (orchestrators with deps injection)
- Layer 5: Renderers (terminal consumers)
- Layer 6: Observability (OpenTelemetry + runs tracking)

**Core Data Contracts**:
- IR v1 schema lockfile (`schema/ir_v1.sql`, `schema/ir_v1.json`)
- Runs table (operational metadata)
- Lineage table (DAG tracking)
- UUID5 namespaces (deterministic, immutable)

**6 Quick Wins** (2 hours total):
- QW-0: IR v1 lockfile + CI check (30 min)
- QW-1: Pandas CI enforcement (5 min)
- QW-2: Slack adapter fail-fast (10 min)
- QW-3: PrivacyPass capability token (45 min)
- QW-4: UUID5 namespaces (20 min)
- QW-5: OpenTelemetry bootstrap (30 min)

**10 Priority Areas** (Weeks 1-12):
- A: Platform Seams & Plugins
- B: Privacy as a Capability
- C: Data Layer Discipline
- D: Observability & Runs Tracking
- E: Agent Boundary Hygiene
- F: Observability & Ops
- G: Reliability & Performance
- H: Security & Secrets
- I: Testing Strategy
- J: CLI & DX

**5 Living ADRs**:
- ADR-001: Sources → Adapters → IR v1
- ADR-002: Privacy as Capability Token
- ADR-003: Ibis-First + SQL Escape Hatch
- ADR-004: Agents as Orchestrators
- ADR-005: Unified CLI + Runs Tracking

---

### 2. **WEEK_1_EXECUTION.md** (255 lines)
Detailed 5-day execution guide with:

**Daily Breakdown**:
- Day 1 (Monday): Schema Foundation (2 hours)
- Day 2 (Tuesday): Privacy Capability (2.5 hours)
- Day 3 (Wednesday): Runs & Lineage (3 hours)
- Day 4 (Thursday): Observability & Checkpoints (3 hours)
- Day 5 (Friday): Golden Test & Doctor (3 hours)

**Total Effort**: 13-15 hours

**Success Criteria** (tiered):
- P0 (Must Have): 5 items
- P1 (Should Have): 4 items
- P2 (Nice to Have): 3 items

---

## Key Architectural Wins

✅ **Versioned IR**: Schema drift detection via lockfile
✅ **Privacy-First**: Capability-based gate (no global state)
✅ **Deterministic**: Content-addressed checkpoints + namespaced UUIDs
✅ **Observable**: Runs table + OpenTelemetry traces
✅ **Pluggable**: Adapter entry points + `adapter_meta()`
✅ **Multi-tenant**: `tenant_id` flows through entire pipeline
✅ **Testable**: Deps injection + property tests

---

## Success Metrics

### Safety
- 0% LLM calls without PrivacyPass
- 0% privacy gate bypasses
- 100% adapter outputs validated

### Determinism
- Re-ingest → identical UUIDs (hash match on 1000 rows)
- Stable fingerprints (same input → same fingerprint)

### Performance
- Vectorized UDFs ≥10× speedup
- <2s checkpoint decision per stage

### Observability
- 100% runs have trace + runs row
- Mean-time-to-explain < 5 min via `egregora runs tail`
- Error budget: ≤1% degraded runs

### Developer Experience
- <5 min to add new adapter (cookiecutter template)
- Golden-path tutorial < 5 min (WhatsApp → site)
- Clear error messages (no raw stack traces)

---

## Next Steps

### Option 1: Start Week 1 Implementation
Execute the 5-day plan from `docs/WEEK_1_EXECUTION.md`:

```bash
# Day 1: Schema Foundation
cd /home/user/egregora
mkdir -p schema
# Create IR v1 lockfile
# Create UUID5 namespaces
# Turn on pandas CI check

# See WEEK_1_EXECUTION.md for detailed steps
```

### Option 2: Review & Refine
- Review roadmap with team
- Adjust timelines based on team size
- Prioritize specific features
- Add/remove Quick Wins

### Option 3: Create PR Scaffold
Generate skeleton implementations:
- IR v1 lockfile templates
- PrivacyPass capability token stub
- Runs table schema
- Doctor command skeleton

---

## Files Created

```
ARCHITECTURE_ROADMAP.md       (1,320 lines) - 90-day comprehensive plan
docs/WEEK_1_EXECUTION.md       (255 lines) - 5-day execution guide
docs/ROADMAP_SUMMARY.md        (this file) - Executive summary
```

**Git Status**:
- Branch: `claude/actionable-plan-011CUur116K7c4WxATK5d2y4`
- Commits: 4 commits
- Ready for: PR or direct merge

---

## What Changed from Original Plan

**From**: Organization improvements (file renames, test moves)
**To**: Comprehensive architecture foundation

**Key Additions**:
1. **Data contracts**: IR v1, runs, lineage tables
2. **Privacy capability**: PrivacyPass token (not global flag)
3. **Content-addressed checkpoints**: SHA256 fingerprints
4. **Multi-tenant ready**: Namespaced UUIDs
5. **Observability**: Runs tracking + OpenTelemetry
6. **Risk register**: 6 risks with mitigations
7. **Week 1 guide**: Day-by-day execution plan

**Philosophy Shift**:
- From: Tactical cleanup
- To: Strategic platform foundation

---

## Recommended Path Forward

### Immediate (This Week)
1. Review `ARCHITECTURE_ROADMAP.md` with team
2. Adjust Week 1 priorities if needed
3. Start Day 1 tasks (Schema Foundation)
4. Set up CI for IR schema drift detection

### Short-term (Weeks 1-2)
1. Complete all 6 Quick Wins
2. Implement runs + lineage tracking
3. Golden WhatsApp test (<5 min)
4. Doctor command

### Medium-term (Weeks 3-6)
1. Privacy capability token
2. Content-addressed checkpoints
3. View registry + StorageManager
4. Agent refactoring (deps injection)

### Long-term (Weeks 7-12)
1. Circuit breaker + backpressure
2. Vectorized UDFs (10× speedup)
3. Unified CLI
4. Adapter plugin system

---

## Questions to Answer

1. **Week 1 Start Date**: When do we begin?
2. **Team Size**: 1 developer or 2+?
3. **Priorities**: Any Quick Wins to skip/defer?
4. **Slack Adapter**: Implement in Week 1 or defer?
5. **Multi-tenant**: Single tenant MVP first?

---

## Resources

**Documentation**:
- `ARCHITECTURE_ROADMAP.md` - Master plan
- `docs/WEEK_1_EXECUTION.md` - Day-by-day guide
- `CLAUDE.md` - Project context (already exists)
- `CONTRIBUTING.md` - TENET-BREAK philosophy (already exists)

**Future Docs** (to be created):
- `docs/architecture/ir-v1-spec.md`
- `docs/architecture/adr-002-privacy-gate.md`
- `docs/architecture/adapter-guide.md`
- `docs/architecture/stages.md`
- `docs/architecture/slos.md`

**Tools**:
- `scripts/check_ir_schema.py` (to be created)
- `scripts/create_runs_tables.py` (to be created)
- `egregora doctor` (to be created)
- `egregora runs tail` (to be created)

---

**Ready to execute**: Week 1 starts whenever you are! 🚀

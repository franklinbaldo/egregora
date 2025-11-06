# Complexity Reduction Documentation

This directory contains the complete planning and evaluation for the Egregora complexity reduction initiative.

## 📁 Document Guide

### 1. **START HERE** → `complexity-reduction-final-plan.md`
The unified, final plan that combines all three initiatives:
- Config migration (.egregora/)
- Pydantic-AI compliance
- Complexity reduction
- Optional architectural improvements

**Read this first** for the complete picture.

### 2. Supporting Documents

#### `complexity-reduction-evaluation.md`
Executive summary of the evaluation process. Shows how we arrived at the final plan.

#### `complexity-reduction-plan-v2.md`
Detailed analysis with modern patterns. **Contains some misrepresentations** that are corrected in the final plan.

⚠️ **Note**: This document proposed patterns that aren't actually standard Pydantic-AI:
- WriterToolSet class (current @agent.tool is correct!)
- Result types for tools (should use BaseModel)
- with_* methods (not documented)

**Use the final plan instead** - it corrects these errors.

#### `complexity-reduction-plan.md` (Original, PR #618)
The baseline tactical plan. Solid foundation, lacks strategic improvements.

#### `development/egregora-config-migration.md`
Detailed config migration plan (Phase 0 of final plan).

#### `pydantic-ai-patterns-review.md`
Critical review that identified misrepresentations in v2.0 plan.

## 🎯 Quick Decision Matrix

| Option | Timeline | Scope | Risk | Recommendation |
|--------|----------|-------|------|----------------|
| **Core Only** | 8 weeks | Config + Compliance + Complexity | Low | ⭐ Good baseline |
| **Core + Parser** | 10 weeks | + pyparsing parser modernization | Low-Med | ⭐⭐⭐ **RECOMMENDED** |
| **Core + Parser + RAG** | 12 weeks | + RAG strategy pattern | Medium | ⭐⭐ Good for extensibility |
| **Full Modernization** | 14 weeks | + Domain value objects | Medium | ⭐ Long-term investment |

## ✅ What's Fixed

All options fix:
- **62 complexity errors** (C901, PLR0913, PLR0915, PLR0912, PLR0911)
- **Pydantic-AI compliance** (deps mutation, parameter counts)
- **Config migration** (.egregora/ directory structure)

Optional phases add:
- **Parser modernization** (pyparsing, 500→200 lines)
- **RAG refactor** (strategy pattern, extensibility)
- **Domain objects** (type safety, validation)

## 🚀 How to Use

1. **Read** `complexity-reduction-final-plan.md`
2. **Choose** an option (Core Only through Full Modernization)
3. **Get approval** for timeline and dependencies
4. **Start with Phase 0** (Config migration)
5. **Execute phases** sequentially
6. **Review after each phase** and adjust if needed

## 📊 Phase Overview

### Phase 0: Config Migration (Week 1-2)
Foundation work - extract settings from mkdocs.yml to .egregora/

### Phase 1: Pydantic-AI Compliance (Week 3)
Fix only the 2 actual framework violations

### Phase 2: Config Objects (Week 4)
Apply dataclass pattern to reduce parameters

### Phase 3: Pipeline Decomposition (Week 5-6)
Extract focused functions from complex orchestrators

### Phase 4: Remaining Complexity (Week 7)
Tactical fixes for avatar, profiler, adapters

### Phase 5: Testing & Integration (Week 8)
Validate, document, clean up

### Phase 6-8: OPTIONAL Improvements
Parser modernization, RAG refactor, domain objects

## ⚠️ Critical Corrections

The v2.0 plan misrepresented some patterns as "standard Pydantic-AI" when they weren't:

### ❌ WRONG (Don't Do)
- Change tool registration to class-based pattern
- Use Result[T, str] for tool returns
- Implement with_* methods for state updates

### ✅ RIGHT (Do This)
- Keep @agent.tool decorator (current is correct!)
- Keep BaseModel returns from tools (current is correct!)
- Fix deps mutation (don't append to lists)
- Use frozen dataclasses for deps

**The final plan uses only documented, verified patterns.**

## 🔗 Related Work

- **PR #618**: Original complexity reduction plan
- **Config Migration**: Separate initiative now integrated as Phase 0
- **Pydantic-AI Review**: Critical feedback that shaped final plan

## 📝 Status

- ✅ Planning complete
- ✅ All documents reviewed and unified
- ⏳ Awaiting approval to begin Phase 0

## 💬 Questions?

See the final plan for:
- Detailed code examples
- Risk mitigation strategies
- Success criteria
- Decision framework
- FAQ section

---

**Recommended**: Read `complexity-reduction-final-plan.md` for the complete, unified approach.

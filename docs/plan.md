# Egregora Refactoring Plan

## Overview

This plan addresses the critical architectural and engineering issues identified in the code analysis. The strategy prioritizes **gradual, low-risk refactoring** to transform Egregora from a schizophrenic text/DataFrame hybrid into a unified, modern, DataFrame-native pipeline.

## Guiding Principles

1. **Incremental Migration**: No "big bang" rewrites. Changes are small, testable, and reversible.
2. **Risk Minimization**: High-impact, low-risk changes first (e.g., library replacements).
3. **DataFrame-Native Architecture**: All data processing should use `polars` DataFrames end-to-end.
4. **Standard Libraries First**: Prefer battle-tested libraries over custom implementations.

---

## Phase 1: Foundation (Low-Risk, High-Impact)

### 1.1 Replace Custom Caching Systems
**Priority: HIGH | Risk: LOW | Effort: LOW**

**Problem**: Two over-engineered custom caching systems reinvent the wheel.

**Action Items**:
- [ ] Add `diskcache` to project dependencies
- [ ] Replace `cache_manager.py` with `diskcache`
  - Update all imports and usages across the codebase
  - Test cache hit/miss behavior matches original
  - Remove `cache_manager.py` once verified
- [ ] Replace `rag/embedding_cache.py` with `diskcache`
  - Update RAG components to use new cache
  - Verify embedding retrieval performance
  - Remove `rag/embedding_cache.py` once verified

**Success Criteria**:
- All caching functionality works identically
- Code complexity reduced significantly
- No custom cache management code remains

---

### 1.2 Adopt Standard Libraries
**Priority: HIGH | Risk: LOW | Effort: LOW**

**Problem**: Hand-rolled implementations for solved problems (date parsing, configuration).

**Action Items**:
- [ ] Replace date parsing with `python-dateutil`
  - Add `python-dateutil` to dependencies
  - Refactor `date_utils.py` to use `dateutil.parser.parse`
  - Add proper error handling and timezone awareness
  - Update tests

- [ ] Migrate configuration to Pydantic
  - Add `pydantic` and `pydantic-settings` to dependencies
  - Refactor `config.py` to use Pydantic models
  - Replace manual TOML parsing with Pydantic validation
  - Refactor `mcp_server/config.py` similarly
  - Update all configuration consumers

**Success Criteria**:
- Robust date parsing with proper error handling
- Type-safe configuration with validation
- Reduced boilerplate code

---

### 1.3 Externalize Hardcoded Data
**Priority: MEDIUM | Risk: LOW | Effort: LOW**

**Problem**: Configuration data hardcoded in Python files.

**Action Items**:
- [ ] Externalize Portuguese stopwords from `analytics.py`
  - Create `config/stopwords_pt.txt` or similar
  - Update `analytics.py` to load from file
  - Make stopword list configurable per language

- [ ] Externalize system message filters from `parser.py`
  - Create `config/system_message_filters.txt` or similar
  - Update `parser.py` to load from file
  - Allow custom filter lists via configuration

**Success Criteria**:
- All data lists are externalized and configurable
- Code is cleaner and more maintainable

---

## Phase 2: Architecture Migration (High-Impact, Medium-Risk)

### 2.1 Audit and Deprecate Legacy Systems
**Priority: HIGH | Risk: MEDIUM | Effort: MEDIUM**

**Problem**: Redundant TF-IDF search system coexists with modern llama-index RAG.

**Action Items**:
- [ ] Audit usage of `rag/search.py` (legacy TF-IDF)
  - Identify all callsites across the codebase
  - Document what functionality it currently provides
  - Compare capabilities with llama-index RAG

- [ ] Create migration path if needed
  - If TF-IDF provides unique value, document why
  - Otherwise, create deprecation plan

- [ ] Deprecate or remove legacy TF-IDF
  - Update all consumers to use llama-index
  - Remove `rag/search.py` and related code
  - Update documentation

**Success Criteria**:
- Single, unified search/RAG system
- No redundant search implementations
- Clear documentation of chosen approach

---

### 2.2 Refactor to DataFrame-Native Pipeline (Core Architecture)
**Priority: HIGH | Risk: HIGH | Effort: HIGH**

**Problem**: "Architectural schizophrenia" between DataFrame-native and text-based processing.

**Strategy**: Gradually move logic from text-based pipeline to DataFrame-native processor.

#### Step 2.2.1: Prepare processor.py
- [ ] Audit current `processor.py` to understand all DataFrame → text conversions
- [ ] Design new DataFrame-native API for processor
- [ ] Create feature flags to toggle between old/new pipeline behaviors

#### Step 2.2.2: Refactor enrichment.py
- [ ] Rewrite URL extraction to use `polars` operations
- [ ] Rewrite context extraction to use `polars` operations
- [ ] Eliminate text conversion in enrichment flow
- [ ] Add tests for DataFrame-based enrichment

#### Step 2.2.3: Refactor media_extractor.py
- [ ] Rewrite to accept and return `polars` DataFrames
- [ ] Update media extraction logic to use DataFrame operations
- [ ] Eliminate text dependencies
- [ ] Add tests for DataFrame-based extraction

#### Step 2.2.4: Refactor profiles feature
- [ ] Update `profiles/` implementation to be DataFrame-native
- [ ] Eliminate text conversions in profile processing
- [ ] Improve documentation on profile feature usage
- [ ] Add tests for DataFrame-based profiles

#### Step 2.2.5: Migrate pipeline.py logic to processor.py
- [ ] Move orchestration logic from `pipeline.py` to `processor.py` incrementally
- [ ] For each function in `pipeline.py`:
  - Rewrite as DataFrame-native in `processor.py`
  - Update consumers to use new version
  - Test thoroughly
  - Remove old version once verified

#### Step 2.2.6: Eliminate transcript.py anti-pattern
- [ ] Update all consumers of `extract_transcript()` to use DataFrames directly
- [ ] Phase out `extract_transcript()` function
- [ ] Keep `load_source_dataframe()` as the primary API
- [ ] Remove transcript text extraction logic

#### Step 2.2.7: Remove pipeline.py
- [ ] Verify all functionality has been migrated
- [ ] Remove `pipeline.py` completely
- [ ] Update documentation to reflect new architecture

**Success Criteria**:
- Single, unified DataFrame-native pipeline
- No DataFrame → text → DataFrame conversions
- `processor.py` is the central orchestrator
- `pipeline.py` is removed
- All components work with `polars` DataFrames

---

## Phase 3: Optimization & Documentation (Low-Risk)

### 3.1 Performance Optimization
**Priority: MEDIUM | Risk: LOW | Effort: MEDIUM**

**Action Items**:
- [ ] Profile DataFrame operations in refactored pipeline
- [ ] Identify and optimize bottlenecks
- [ ] Add lazy evaluation where beneficial
- [ ] Optimize memory usage for large datasets

### 3.2 Documentation Updates
**Priority: MEDIUM | Risk: LOW | Effort: MEDIUM**

**Action Items**:
- [ ] Update architecture documentation to reflect DataFrame-native design
- [ ] Document the unified pipeline flow
- [ ] Create migration guide for users of old API
- [ ] Update API documentation
- [ ] Document configuration options for externalized data

### 3.3 Testing & Validation
**Priority: HIGH | Risk: LOW | Effort: MEDIUM**

**Action Items**:
- [ ] Ensure comprehensive test coverage for refactored components
- [ ] Add integration tests for end-to-end DataFrame pipeline
- [ ] Add performance benchmarks
- [ ] Create regression tests to prevent architectural backsliding

---

## Implementation Timeline

### Sprint 1 (Week 1-2): Foundation
- Replace custom caching systems
- Adopt standard libraries (dateutil, Pydantic)
- Externalize hardcoded data

### Sprint 2 (Week 3-4): Legacy Cleanup
- Audit and deprecate TF-IDF system
- Begin DataFrame-native refactoring of enrichment.py

### Sprint 3 (Week 5-6): Core Migration
- Refactor media_extractor.py and profiles
- Begin migrating pipeline.py logic to processor.py

### Sprint 4 (Week 7-8): Completion
- Complete pipeline.py migration
- Eliminate transcript.py anti-pattern
- Remove pipeline.py

### Sprint 5 (Week 9-10): Polish
- Performance optimization
- Documentation updates
- Final testing and validation

---

## Risk Mitigation

1. **Rollback Strategy**: Use feature flags and maintain parallel implementations during migration
2. **Testing**: Comprehensive test suite at each step before proceeding
3. **Incremental Deployment**: Deploy changes incrementally, monitor for issues
4. **Documentation**: Keep detailed migration notes for debugging

---

## Success Metrics

- **Code Quality**:
  - Elimination of all custom implementations with standard library equivalents
  - Single, unified data processing architecture
  - No DataFrame ↔ text conversions

- **Performance**:
  - No regression in processing speed
  - Reduced memory usage from efficient DataFrame operations

- **Maintainability**:
  - Reduced codebase complexity
  - Clear separation of concerns
  - Improved documentation

- **Architecture**:
  - DataFrame-native end-to-end
  - No architectural "schizophrenia"
  - Clean, modern codebase aligned with best practices

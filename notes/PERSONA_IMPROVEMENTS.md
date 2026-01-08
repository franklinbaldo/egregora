# Persona Prompt Improvements for .jules/

## Executive Summary

After reviewing all persona prompts, I've identified opportunities to improve consistency, clarity, and effectiveness across the Jules agent system.

## 1. Structural Improvements

### 1.1 Standardize Section Order

**Current State:** Personas have inconsistent section ordering (some start with TDD, others with philosophy, others with process).

**Recommendation:** Adopt a standard structure:

```markdown
---
[frontmatter]
---
You are "[Name]" [emoji] - [one-line description]

{{ identity_branding }}

{{ pre_commit_instructions }}

## Philosophy / Core Principle
[The "why" - 2-3 paragraphs max]

## The Law: Test-Driven Development (TDD)
[TDD specific to this persona's domain]

## The [Persona Name] Process
[Main workflow with clear numbered steps]

{{ empty_queue_celebration }}

{{ journal_management }}

## Guardrails
[Always do / Never do]

## Examples (Optional)
[Concrete examples]
```

**Impact:** Easier onboarding, faster context switching between personas.

---

## 2. Content Improvements

### 2.1 Add "Success Metrics" Section

**Current State:** Personas describe what to do but not how to measure success.

**Recommendation:** Add a "Success Metrics" section after the philosophy:

```markdown
## Success Metrics

You're succeeding when:
- [Metric 1: e.g., "PRs have < 3 files changed"]
- [Metric 2: e.g., "Test coverage increases"]
- [Metric 3: e.g., "No security vulnerabilities in audits"]

You're NOT succeeding if:
- [Anti-pattern 1: e.g., "PRs sit for > 1 week"]
- [Anti-pattern 2: e.g., "Tests are skipped"]
```

**Affected Personas:** All (especially Simplifier, Essentialist, Sentinel, Artisan)

**Example for Essentialist:**
```markdown
## Success Metrics

You're succeeding when:
- Each PR removes more lines than it adds
- Abstractions have 2+ implementations
- New developers understand the code faster

You're NOT succeeding if:
- You're creating new abstractions
- PRs require extensive documentation to explain changes
- Test complexity increases
```

---

### 2.2 Strengthen the "Philosophy" Section

**Current State:** Some personas (Simplifier, Essentialist) have strong philosophical foundations. Others (Builder, Scribe) jump straight to process.

**Recommendation:** Every persona should have a 2-3 paragraph philosophy section that answers:
1. **What problem does this persona solve?**
2. **What is the core principle/belief?**
3. **How does this differ from adjacent personas?**

**Example for Builder (current version is weak):**
```markdown
## Philosophy: Structure Before Scale

Bad schemas are technical debt that compounds. Every table without constraints, every untyped column, every missing index is a future incident waiting to happen.

Your job isn't to build what's requested—it's to build what's *right*. If a feature requires a new table, that table should be designed to last 5 years, not 5 sprints.

Unlike Artisan (who improves existing code) or Simplifier (who removes complexity), you're a foundation engineer. You prevent problems by making invalid states unrepresentable.
```

**Affected Personas:** Builder, Scribe, Forge, Curator

---

### 2.3 Make TDD Instructions More Specific

**Current State:** TDD sections are generic. "Write a test" doesn't guide what KIND of test.

**Recommendation:** Make TDD instructions domain-specific with concrete examples.

**Example for Sentinel (security):**
```markdown
### 1. 🔴 RED - Write the Exploit Test

Create a test that demonstrates the vulnerability:

**Example (SSRF vulnerability):**
```python
def test_ssrf_protection():
    """Verify that SSRF attacks are blocked."""
    # Try to access internal metadata endpoint
    response = client.fetch_url("http://169.254.169.254/latest/meta-data/")
    assert response.status_code == 403
    assert "blocked" in response.json()["error"]
```

**Key requirements:**
- Test MUST fail initially (proving the exploit works)
- Test should be safe to run (no real damage)
- Test should use realistic attack vectors from OWASP
```

**Example for Builder (schema migrations):**
```markdown
### 1. 🔴 RED - Write the Schema Test

**Example (adding a new required column):**
```python
def test_migration_adds_author_column():
    # Verify old schema doesn't have column
    with pytest.raises(ColumnNotFoundError):
        db.query("SELECT author_id FROM posts")

    # Run migration
    migrate_to_v2()

    # Verify new schema has column with constraints
    result = db.query("SELECT author_id FROM posts WHERE id = 1")
    assert result["author_id"] is not None  # NOT NULL constraint
```

**Key requirements:**
- Test the migration path, not just the final state
- Verify constraints (NOT NULL, UNIQUE, FOREIGN KEY)
- Test with realistic existing data
```

**Affected Personas:** All personas that use TDD

---

### 2.4 Add "Common Pitfalls" Section

**Current State:** Personas describe what TO do but not what mistakes are common.

**Recommendation:** Add a "Common Pitfalls" section before Guardrails:

```markdown
## Common Pitfalls

### ❌ Pitfall: [Mistake Name]
**What it looks like:** [Concrete example]
**Why it's wrong:** [Explanation]
**Instead, do this:** [Better approach]
```

**Example for Simplifier:**
```markdown
## Common Pitfalls

### ❌ Pitfall: Deleting Abstractions That ARE Used
**What it looks like:** "This interface has only one implementation, so I'll inline it."
**Why it's wrong:** The interface might be a seam for testing, or a boundary for a future plugin system.
**Instead, do this:** Check git history. If the interface was added recently with explicit rationale, respect it. If it's legacy and tests don't use it, proceed.

### ❌ Pitfall: Simplifying at the Wrong Granularity
**What it looks like:** Focusing on individual functions instead of architectural layers.
**Why it's wrong:** You optimize for LOC instead of cognitive load.
**Instead, do this:** Focus on "conceptual compression" — fewer modules, fewer patterns, fewer frameworks.
```

**Affected Personas:** All (especially Simplifier, Essentialist, Sapper, Artisan)

---

### 2.5 Clarify Persona Boundaries

**Current State:** Overlap between similar personas (Simplifier vs Essentialist, Artisan vs Refactor, Scribe vs Docs Curator).

**Recommendation:** Add explicit boundary statements in the Philosophy section.

**Example additions:**

**Simplifier:**
```markdown
## When NOT to Act

- **Don't touch code with active feature work** (check recent commits/PRs)
- **Don't simplify if it makes onboarding HARDER** (sometimes explicit is better than clever)
- **Defer to Essentialist** when the issue is about principles/heuristics rather than code structure
```

**Essentialist:**
```markdown
## Boundaries with Other Personas

- **vs Simplifier:** You focus on *architectural* complexity (layers, frameworks). Simplifier focuses on *implementation* complexity (abstractions, indirection).
- **vs Artisan:** You enforce principles via deletion. Artisan improves quality via addition (docs, types, tests).
- **vs Sapper:** You prevent complexity. Sapper fixes exception handling.
```

**Affected Personas:** Simplifier, Essentialist, Artisan, Scribe, Docs Curator

---

## 3. Consistency Fixes

### 3.1 Standardize TDD Step Naming

**Current State:** Some personas use "🔴 RED", others use "1. 🔴 RED - Write the Test"

**Recommendation:** Use consistent formatting:
```markdown
### 1. 🔴 RED - [Action]
### 2. 🟢 GREEN - [Action]
### 3. 🔵 REFACTOR - [Action]
```

---

### 3.2 Standardize "Process" Section Naming

**Current State:** Varies between "The Process", "The Daily Routine", "The [Name] Process", "The Defusal Process"

**Recommendation:** Use `## The [Persona Name] Process` for consistency, unless there's a strong thematic reason (like Sapper's "Defusal Process").

---

### 3.3 Standardize Guardrails Format

**Current State:** Some personas use "✅ Always do / 🚫 Never do", others use "Boundaries", others have it scattered.

**Recommendation:** Standardize as:
```markdown
## Guardrails

### ✅ Always do:
- [Item 1]
- [Item 2]

### ⚠️ Exercise Judgment:
- [Item 1 with context]

### 🚫 Never do:
- [Item 1]
- [Item 2]
```

---

## 4. Missing Personas

Based on common patterns in journals and the codebase, consider adding:

### 4.1 "Archaeologist" 📜
**Focus:** Git history analysis, understanding why decisions were made, documenting legacy rationale
**When to use:** Before major refactors, when encountering "why is this here?" code

### 4.2 "Navigator" 🧭
**Focus:** Dependency management, import hygiene, circular dependency detection
**When to use:** When modules import each other in confusing ways, when dependency tree is too deep

### 4.3 "Gardener" 🌱
**Focus:** Comment hygiene, outdated TODO removal, keeping inline docs fresh
**When to use:** When comments lie, when TODOs are 2+ years old

---

## 5. Template Variables Improvements

### 5.1 Add `{{ persona_scope }}`

**Current State:** Each persona manually describes its scope.

**Recommendation:** Add a standard scope injection:

```python
# In scheduler.py
PERSONA_SCOPE = """
## Scope

You operate on: {{ target_paths | default('entire repository') }}
You ignore: {{ exclude_paths | default('none') }}
Typical PR size: {{ typical_pr_lines | default('< 200 lines') }}
"""
```

Then personas can override in frontmatter:
```yaml
target_paths: ["egregora/core", "egregora/adapters"]
exclude_paths: ["tests/", "docs/"]
typical_pr_lines: "< 100 lines"
```

---

### 5.2 Add `{{ testing_strategy }}`

**Current State:** Testing expectations are implicit.

**Recommendation:** Make test expectations explicit:

```python
TESTING_STRATEGY = """
## Testing Requirements

{{ test_requirement_level | default('Required for all changes') }}

Run tests with:
```bash
uv run pytest {{ test_path_filter | default('') }}
```

Coverage threshold: {{ coverage_threshold | default('No decrease') }}
"""
```

---

## 6. Specific Persona Fixes

### 6.1 Weaver (PROMPT.md)

**Issue:** Lives in `.jules/jules/PROMPT.md` instead of `.jules/personas/weaver/prompt.md`

**Impact:** Inconsistent with other personas, harder to discover

**Recommendation:** Move to standard location and add frontmatter

---

### 6.2 Sapper

**Issue:** "Trigger, Don't Confirm" philosophy is excellent but could use more examples

**Recommendation:** Add a "Before/After" section:

```markdown
## Before/After Examples

### ❌ Before (LBYL - Look Before You Leap)
```python
def get_user(user_id):
    user = db.query(user_id)
    if user is None:
        return None
    if not user.is_active:
        return None
    return user
```

### ✅ After (EAFP - Easier to Ask Forgiveness than Permission)
```python
def get_user(user_id):
    try:
        user = db.query(user_id)
        if not user.is_active:
            raise UserInactiveError(user_id)
        return user
    except UserNotFoundError:
        raise  # Let caller handle
```
```

---

### 6.3 Essentialist

**Issue:** The heuristics list is excellent but overwhelming (24 items)

**Recommendation:** Group into tiers:

```markdown
## The Essentialist Heuristics

### 🔥 Tier 1: Start Here (High Impact, Low Risk)
- Delete over deprecate
- Duplication over premature abstraction
- Simple defaults over smart defaults

### ⚡ Tier 2: Medium Complexity
- Declarative over imperative
- Composition over inheritance
- Constraints over options

### 🎯 Tier 3: Advanced (Requires Context)
- Data over logic
- Filesystem over database (when it fits)
- Batch over streaming
```

---

### 6.4 Sentinel

**Issue:** Missing concrete OWASP mapping

**Recommendation:** Add a checklist:

```markdown
## OWASP Top 10 Checklist

- [ ] **A01 - Broken Access Control:** Check auth boundaries
- [ ] **A02 - Cryptographic Failures:** Verify secrets not in code
- [ ] **A03 - Injection:** Validate SQL/command inputs
- [ ] **A04 - Insecure Design:** Review threat model
- [ ] **A05 - Security Misconfiguration:** Check default passwords
- [ ] **A06 - Vulnerable Components:** Run `uv run pip-audit`
- [ ] **A07 - Authentication Failures:** Test session management
- [ ] **A08 - Software Integrity:** Verify SRI for CDN assets
- [ ] **A09 - Logging Failures:** Ensure audit logs exist
- [ ] **A10 - SSRF:** Check URL fetching code
```

---

## 7. Priority Implementation Order

1. **High Priority (Do First):**
   - 2.2: Strengthen philosophy sections
   - 3.1-3.3: Consistency fixes
   - 2.3: Domain-specific TDD examples

2. **Medium Priority:**
   - 2.1: Success metrics
   - 2.4: Common pitfalls
   - 2.5: Persona boundaries

3. **Low Priority (Nice to Have):**
   - 4: New personas
   - 5: Template variable improvements
   - 6.1-6.4: Specific fixes

---

## 8. Implementation Strategy

### Option A: Incremental (Recommended)
1. Pick 3 pilot personas (e.g., Essentialist, Sentinel, Artisan)
2. Apply all improvements
3. Observe 2 weeks of Jules runs
4. Refine based on journal entries
5. Roll out to remaining personas

### Option B: Big Bang
1. Update all personas at once
2. Risk: harder to identify what changes helped vs hurt

---

## Appendix: Persona Comparison Matrix

| Persona | Philosophy Strength | TDD Specificity | Examples | Guardrails | Overall Grade |
|---------|-------------------|-----------------|----------|------------|---------------|
| Essentialist | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | A |
| Simplifier | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | A |
| Sapper | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | A+ |
| Sentinel | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | B+ |
| Artisan | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | A |
| Builder | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | C+ |
| Scribe | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | C+ |

**Legend:**
- Philosophy: How well does it explain the "why"?
- TDD Specificity: How actionable are the TDD instructions?
- Examples: Concrete before/after examples?
- Guardrails: Clear always/never rules?

# Investigation: Why Some Jules Personas Don't Create Journals

## Summary

**Issue**: 3 personas (docs_curator, organizer, pruner) are not creating journal entries despite having journal instructions in their prompts.

**Root Cause**: The template rendering works correctly, but the LLM agents are not following the journal creation instructions, likely because they are not prominent enough or clearly mandatory.

## Investigation Findings

### Personas Status

**Total personas**: 20

**With journals directories**: 16
- artisan, bolt, builder, curator, essentialist, forge, janitor, palette, refactor, sapper, scribe, sentinel, shepherd, sheriff, simplifier, visionary

**Without journals directories**: 4
- docs_curator ❌ (uses `{{ journal_management }}`, last ran Dec 25)
- organizer ❌ (uses `{{ journal_management }}`, unknown last run)
- pruner ❌ (uses `{{ journal_management }}`, unknown last run)
- weaver ✅ (doesn't use journal_management at all - expected)

### Key Evidence

1. **Template rendering works correctly**: Test confirmed that `{{ journal_management }}` properly expands to journal instructions

2. **Docs_curator example**:
   - Has `{{ journal_management }}` in prompt (line 88)
   - Last ran on Dec 25, 2025 (commit 23d017e)
   - Successfully created PR #1628
   - Did NOT create journal entry
   - Journal instructions were present in prompt at runtime

3. **Comparison with working personas**:
   - Visionary: Uses custom inline journal instructions as explicit step 4 + `{{ journal_entries }}`
   - Sapper: Uses `{{ journal_management }}` and DOES create journals
   - Both have journal creation after PR creation step

### Template Structure

**JOURNAL_MANAGEMENT template** (scheduler.py lines 24-49):
```markdown
### 📝 DOCUMENT - Update Journal
- Create a NEW file in `.team/personas/{{ id }}/journals/`
- Naming convention: `YYYY-MM-DD-HHMM-Any_Title_You_Want.md`
- **CRITICAL:** Start with YAML Frontmatter...

## Previous Journal Entries
{{ journal_entries }}
```

### Identified Issues

1. **Not mandatory enough**: Instructions say "Create a NEW file" but don't say "MUST" or make it clear this is required

2. **Position in workflow**: Journal instructions come AFTER "Create the PR" step, which might signal to LLM that PR creation is the final task

3. **Not part of numbered workflow**: Personas that work best (like visionary) have journal creation as an explicit numbered step in their process

4. **Directory creation**: If journals directory doesn't exist, LLM might not think to create it first

5. **No validation**: No mechanism checks if journals were created

## Proposed Fixes

### 1. Enhance JOURNAL_MANAGEMENT Template (High Priority)

Make journal creation explicitly mandatory:

```markdown
### 📝 DOCUMENT - Update Journal (REQUIRED)

**CRITICAL: You MUST create a journal entry before finishing your session.**

1. Create the directory `.team/personas/{{ id }}/journals/` if it doesn't exist
2. Create a NEW file: `YYYY-MM-DD-HHMM-Descriptive_Title.md`
3. Use this EXACT format:
   \```markdown
   ---
   title: "{{ emoji }} Your Title"
   date: YYYY-MM-DD
   author: "{{ id | title }}"
   emoji: "{{ emoji }}"
   type: journal
   ---

   ## {{ emoji }} YYYY-MM-DD - Topic
   **Observation:** [What did you notice in the codebase?]
   **Action:** [What changes did you make?]
   **Reflection:** [What should be tackled next? This is REQUIRED.]
   \```

**This journal entry is NOT optional. Create it even if you found no work to do.**

## Previous Journal Entries
{{ journal_entries }}
```

### 2. Restructure Persona Workflows (Medium Priority)

For personas using `{{ journal_management }}`, move it to be part of the main workflow steps, not after:

**Before**:
```
### 4. 🎁 DELIVER - Create the PR
{{ journal_management }}
```

**After**:
```
### 4. 🎁 DELIVER - Create the PR
...

### 5. 📝 DOCUMENT - Journal Entry
{{ journal_management }}
```

### 3. Add Automatic Directory Creation (Low Priority)

Modify `scheduler.py` to automatically create journals directories:

```python
def ensure_journals_directory(persona_dir: Path) -> None:
    """Ensure the journals directory exists for a persona."""
    journals_dir = persona_dir / "journals"
    journals_dir.mkdir(parents=True, exist_ok=True)
```

### 4. Add Journal Validation (Future Enhancement)

Could add a post-run check to verify journal was created and warn if missing.

## Recommended Action

1. **Immediate**: Update JOURNAL_MANAGEMENT template to make journal creation explicitly mandatory
2. **Short-term**: Update the 3 affected personas (docs_curator, organizer, pruner) to have journal creation as an explicit numbered step
3. **Medium-term**: Add automatic journals directory creation
4. **Long-term**: Consider adding validation/warnings for missing journals

## Files to Modify

1. `.team/repo/scheduler.py` - Update JOURNAL_MANAGEMENT constant (line 24-49)
2. `.team/personas/docs_curator/prompt.md` - Restructure workflow
3. `.team/personas/organizer/prompt.md` - Restructure workflow
4. `.team/personas/pruner/prompt.md` - Restructure workflow

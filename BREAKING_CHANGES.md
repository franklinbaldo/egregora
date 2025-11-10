# Breaking Changes - PR #627 Regression Fixes

**Date**: 2025-11-10
**Branch**: `claude/fix-pr627-regressions-011CUzFoSeSDmVRruHbDwTzu`
**Status**: Alpha - No backward compatibility or migrations provided

This document describes breaking changes introduced to fix critical regressions identified in PR #627 testing.

## Philosophy: Alpha Mindset

Per CLAUDE.md, Egregora follows an "alpha mindset":
- ✅ Breaking changes are acceptable and documented
- ❌ No backward compatibility shims
- ❌ No migration scripts
- ✅ Users must adapt to new architecture (delete old output, regenerate)

---

## Summary of Changes

| Issue | Severity | Fixed | Description |
|-------|----------|-------|-------------|
| Folder structure | P1 | ✅ | Content now at root (media/, profiles/, posts/) not in docs/ |
| mkdocs.yml location | P2 | ✅ | Moved to .egregora/mkdocs.yml |
| Prompt copying | P1 | ✅ | Default prompts copied to .egregora/prompts/ during init |
| Post filenames | P1 | ✅ | Clean format: 2025-03-02-slug.md (no spaces/timestamps) |
| Post dates | P1 | ✅ | Clean YYYY-MM-DD in front-matter (not window labels) |
| Profile metadata | P0 | ✅ | YAML front-matter with structured data |
| .authors.yml | P0 | ✅ | Auto-generated for MkDocs blog plugin |
| URL enrichment | P0 | ✅ | Better prompts for higher quality |
| **Post-merge bugs** | | | **Discovered during real data testing** |
| Path resolution bug | P0 | ✅ | site_root incorrectly resolved to .egregora/ instead of root |
| Banner path bug | P1 | ✅ | Banners saved to posts/ instead of media/banners/ |

---

## 1. Folder Structure Reorganization (P1 + P2)

### What Changed

**Old Structure**:
```
site/
├── mkdocs.yml
└── docs/
    ├── media/
    ├── profiles/
    └── posts/
```

**New Structure**:
```
site/
├── .egregora/
│   ├── mkdocs.yml          # ✨ Moved here
│   ├── config.yml
│   └── prompts/            # ✨ New: version pinning
├── media/                  # ✨ At root
├── profiles/               # ✨ At root
└── posts/                  # ✨ At root
    └── journal/            # ✨ New: agent logs
```

### Migration

Delete old output and regenerate:

```bash
rm -rf old-site/
egregora init new-site/
egregora process export.zip --output=new-site/
```

---

## 2. Post Filenames (P1)

**Old**: `2025-03-02 08:01 to 12:49-post-title.md`
**New**: `2025-03-02-post-title.md`

✅ No spaces, no window timestamps
✅ Better URLs and SEO

---

## 3. Post Dates (P1)

**Old front-matter**:
```yaml
date: 2025-03-02 08:01 to 12:49
```

**New front-matter**:
```yaml
date: 2025-03-02
```

---

## 4. Profile Front-Matter (P0)

Profiles now include YAML metadata:

```markdown
---
uuid: d944f0f7
name: Casey
alias: Casey
avatar: https://example.com/avatar.jpg
bio: AI researcher
---

**Writing Style:** [...]
```

---

## 5. .authors.yml Generation (P0)

Auto-generated at `site/.authors.yml`:

```yaml
d944f0f7:
  name: Casey
  description: "[...]"
  avatar: https://example.com/avatar.jpg
```

Enables MkDocs Material blog features (author cards, archives).

---

## 6. Post-Merge Bug Fixes (P0 + P1)

**Discovered**: During real data testing with 31,855 messages
**Fixed**: 2025-11-10 (same day as merge)

### Bug 1: Path Resolution (P0 - Critical)

**Problem**: When `mkdocs.yml` was moved to `.egregora/`, the `resolve_site_paths()` function incorrectly calculated `site_root` as `.egregora/` instead of the actual site root. This caused ALL content directories to be created inside `.egregora/`:

```
WRONG:
.egregora/
├── mkdocs.yml
├── posts/          # ❌ Should be at root!
├── profiles/       # ❌ Should be at root!
└── media/          # ❌ Should be at root!
```

**Root Cause**: Code used `site_root = mkdocs_path.parent` which gives `.egregora/` when `mkdocs_path = site/.egregora/mkdocs.yml`.

**Fix**: Check if mkdocs.yml is in `.egregora/` and go up 2 levels instead of 1:
```python
if mkdocs_path.parent.name == ".egregora":
    site_root = mkdocs_path.parent.parent  # Go up 2 levels
```

**File**: `src/egregora/config/site.py:157-178`

### Bug 2: Banner Path & Naming (P1 - High)

**Problem**: Banner generation had two issues:
1. Saved to `posts/banner-{slug}.png` instead of site root
2. Used slug-based names instead of content-based UUIDs
3. Not integrated with enrichment pipeline

**Root Cause**: `WriterAgentState` didn't have `site_root` field, and banner naming didn't follow media conventions.

**Fix**:
1. Added `site_root: Path | None` to `WriterAgentState`
2. Pass `site_root` when creating state
3. Changed banner naming to use **content-based UUID5** (deterministic, like other media)
4. Save to `site_root / "media" / "images"` (not `media/banners/`)
5. Banners now go through enrichment pipeline like any other media

**Before**:
```
posts/banner-my-post-slug.png  # ❌ Wrong location, slug-based name
```

**After**:
```
media/images/1834adb0-3a27-5208-ab97-a5ed9f2867ea.png  # ✅ Content-based UUID
```

**Files**:
- `src/egregora/agents/banner/generator.py:117-121` (UUID5 generation)
- `src/egregora/agents/writer/agent.py:165,534,582` (path + state)
- `src/egregora/agents/writer/handlers.py:206` (legacy path)

---

## Testing Checklist

After regenerating:

- [ ] Posts at root (not in docs/)
- [ ] Post filenames have no spaces
- [ ] Post dates are YYYY-MM-DD
- [ ] Profiles have YAML front-matter
- [ ] .authors.yml exists
- [ ] mkdocs.yml in .egregora/
- [ ] Prompts in .egregora/prompts/

---

## Questions?

Report issues at: https://github.com/franklinbaldo/egregora/issues

**Remember**: Alpha software - breaking changes are expected.

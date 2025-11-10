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

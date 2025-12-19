# Forge's Journal

Critical implementation learnings from building UX/UI improvements for Egregora MkDocs sites.

---

## 2025-12-19 - Forge Persona Created

**Challenge:** Need systematic workflow to implement Curator's UX vision into actual code changes.

**Solution:** Created Forge persona to:
- Pick high-priority items from `curator.TODO.md`
- Implement CSS/HTML/MkDocs config changes
- Test across viewports and run Lighthouse audits
- Document changes and update TODO
- Ship small, iterate toward excellence

**Result:** Two-persona workflow established:
1. **Curator** 🎭 - Evaluates UX, creates opinionated TODO
2. **Forge** 🔨 - Implements TODO items, tests, ships

**Next Steps:**
- Implement first item from curator.TODO.md
- Establish before/after metrics pattern
- Document common MkDocs customization patterns

---

## Template for Future Entries

```markdown
## YYYY-MM-DD - [Implementation Task]

**Challenge:** [What was tricky about this implementation?]

**Solution:** [How did you solve it? Include code snippets]

**Result:** [Before/after metrics, visual improvements, Lighthouse scores]

**Learnings:** [Reusable patterns, gotchas to avoid]
```

---

## Key Patterns Discovered

### MkDocs Material Customization
_To be filled in as we learn the best ways to customize the theme_

### CSS Techniques That Work Well
_Document successful approaches (spacing systems, responsive typography, etc.)_

### Common Gotchas
_Things that break easily, mobile layout issues, etc._

### Performance Optimizations
_Techniques that improve Lighthouse scores_

---

## Before/After Metrics Template

When documenting implementations, include:

**Before:**
- Lighthouse Performance: ___ / 100
- Lighthouse Accessibility: ___ / 100
- Line length: ___ characters
- Font size: ___ px
- Contrast ratio: ___:1
- Screenshot: [link]

**After:**
- Lighthouse Performance: ___ / 100 (Δ: +/- ___)
- Lighthouse Accessibility: ___ / 100 (Δ: +/- ___)
- Line length: ___ characters (Δ: +/- ___)
- Font size: ___ px (Δ: +/- ___)
- Contrast ratio: ___:1 (Δ: +/- ___)
- Screenshot: [link]

**Impact:** [User-facing improvement description]

---

**Note:** This journal is for critical implementation learnings only.
Focus on:
- Non-obvious solutions to tricky problems
- Reusable patterns and techniques
- Before/after metrics showing measurable improvement
- Gotchas and how to avoid them

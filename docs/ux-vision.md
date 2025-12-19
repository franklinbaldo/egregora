# Egregora UX/UI Vision

**Living design vision for Egregora-generated MkDocs blogs.**

> **Note:** This document starts minimal and grows over time as Curator discovers patterns, tests hypotheses, and documents what works. Curator is responsible for developing this vision through systematic evaluation and comparative analysis.

Last updated: 2025-12-19

---

## Vision Statement

Egregora-generated blogs should be **beautiful, readable, and privacy-respecting**.

**Blog-Specific Focus:**
- This is a **blog format** (narrative, chronological, personal) - not reference documentation
- Optimize for **reading flow** and **storytelling** over quick reference lookup
- Balance **personality** with professionalism
- Support long-form content (2000+ word posts)

**User Goals:**
- Read and understand their data through generated narratives
- Feel confident their privacy is respected
- Navigate chronological content easily
- Enjoy the reading experience

---

## Design Principles

### 1. Privacy-First Visual Identity

**Established:**
- No surveillance imagery (no eyeballs, tracking, data harvesting visuals)
- Emphasize user control and transparency

**To Be Developed by Curator:**
- Color palette that evokes privacy and trust
- Typography choices
- Visual language (shapes, patterns, illustrations)

### 2. Blog-Optimized Reading Experience

**Established:**
- Optimal line length for long-form reading: 45-75 characters
- Support for chronological navigation (date-based)
- Clear post/article hierarchy

**To Be Developed by Curator:**
- Typography scale for blog posts
- Reading time indicators
- Post metadata display (date, tags, etc.)
- Comment/feedback affordances (if applicable)

### 3. Accessibility is Non-Negotiable

**Minimum Standards:**
- WCAG AA compliance (4.5:1 contrast for text)
- Keyboard navigation works
- Screen reader compatible

**Aspirational:**
- WCAG AAA (7:1 contrast)

### 4. Performance Matters

**Targets:**
- Lighthouse Performance: 90+ / 100 (ship threshold)
- First paint < 2 seconds

**To Be Developed by Curator:**
- Specific optimization strategies
- Image handling for blog posts

### 5. Mobile-First

**Established:**
- Must work on mobile devices
- No horizontal scroll
- Touch-friendly navigation

**To Be Developed by Curator:**
- Specific mobile optimizations for blog layout
- Touch target sizes
- Mobile typography

---

## Best-in-Class Blog References

**To Evaluate Against:**
- [Stripe Blog](https://stripe.com/blog) - Clean, professional, great typography
- [Linear Blog](https://linear.app/blog) - Minimalist, elegant, perfect reading experience
- [Tailwind Blog](https://tailwindcss.com/blog) - Beautiful design, great code examples
- [Astro Blog](https://astro.build/blog) - Excellent navigation, personality
- [Daring Fireball](https://daringfireball.net/) - Classic blog readability

**Curator Task:** Compare generated blogs against these and document what makes them excellent.

---

## Discovered Patterns

> **Curator fills this in** as patterns emerge from evaluations.

### What Works Well
_To be documented through evaluation_

### Common Issues
_To be documented through evaluation_

### Validated Improvements
_To be documented with before/after metrics_

---

## Design System (To Be Developed)

### Typography
**Status:** Not yet defined
**Curator Task:** Evaluate and document optimal typography for blog reading

### Color Palette
**Status:** Not yet defined
**Curator Task:** Develop privacy-focused color palette through testing

### Spacing System
**Status:** Not yet defined
**Curator Task:** Document spacing patterns that improve readability

---

## Template Architecture

**Important:** Egregora generates MkDocs sites using **templates located in `src/`** (specific location TBD).

**Workflow:**
1. **DON'T** edit `demo/` directly (it's generated output)
2. **DO** edit templates in `src/` (propagates to all generated sites)
3. **Test** by regenerating demo: `uv run egregora demo`

**Curator & Forge:** Identify template location in `src/` and document here.

---

## Lighthouse Targets

### Minimum (Ship Threshold)
- Performance: **90+** / 100
- Accessibility: **95+** / 100

### Aspirational (Excellence)
- Performance: **95+** / 100
- Accessibility: **100** / 100

---

## Related Documents

- **[TODO.ux.md](../TODO.ux.md)** - Current UX/UI tasks
- **[.jules/curator.md](../.jules/curator.md)** - Curator's evaluation journal
- **[.jules/forge.md](../.jules/forge.md)** - Forge's implementation journal

---

## How to Use This Document

**For Curator:**
- Start with this minimal foundation
- Evaluate generated blogs against best-in-class references
- Document discoveries in "Discovered Patterns" section
- Develop design system through systematic testing
- Update this document as understanding grows

**For Forge:**
- Reference established principles for design decisions
- Implement changes in `src/` templates (not `demo/`)
- Validate changes propagate to generated sites
- Document successful patterns back into this vision

---

**This is a living document.** It starts minimal and grows through Curator's systematic evaluation and Forge's implementation learnings. Don't prescribe everything upfront - discover what works through testing.

# Curator TODO - UX/UI Task List

Last updated: 2025-12-19
Demo version: Current main branch

**📖 Vision Document:** See **[docs/ux-vision.md](docs/ux-vision.md)** for strategic vision, design principles, and excellence criteria.

**Workflow:**
1. **Curator** 🎭 evaluates UX/UI against [vision](docs/ux-vision.md) and updates this TODO
2. **Forge** 🔨 implements items from this TODO, guided by [vision](docs/ux-vision.md)

## High Priority (Critical for Excellence)

### 🛠️ Infrastructure & Tooling
- [ ] Add `egregora demo` CLI command for easy demo generation
- [ ] Create test to ensure demo/ stays updated with code changes
- [ ] Set up automated Lighthouse CI for regression detection
- [ ] Add visual regression testing (Percy or similar)

### 📊 Baseline Measurement (Do This First)
- [ ] Generate current demo and run Lighthouse audit
- [ ] Document baseline scores (Performance, A11y, Best Practices, SEO)
- [ ] Take screenshots of current state for before/after comparison
- [ ] Test on mobile devices (actual phones, not just DevTools)

### 🎨 Visual Design Fundamentals
- [ ] Audit current color palette against WCAG AA (4.5:1 contrast)
- [ ] Evaluate typography scale and hierarchy
- [ ] Measure line length (should be 45-75 characters)
- [ ] Check spacing consistency (is there a system?)
- [ ] Review mobile responsive behavior

### 📖 Content & Readability
- [ ] Test readability with Flesch-Kincaid score (target: 60+)
- [ ] Check heading hierarchy (proper H1→H2→H3 nesting)
- [ ] Evaluate scannability (can you skim and find info?)
- [ ] Review code block syntax highlighting
- [ ] Test search functionality (does it return relevant results?)

### ♿ Accessibility Compliance
- [ ] Run axe DevTools audit (fix all critical/serious issues)
- [ ] Test keyboard navigation (can you tab through everything?)
- [ ] Verify screen reader compatibility (NVDA/JAWS/VoiceOver)
- [ ] Check color contrast (WCAG AA minimum, AAA target)
- [ ] Ensure all images have descriptive alt text

## Medium Priority (Refinement & Polish)

### 🧭 Navigation & Wayfinding
- [ ] Add breadcrumbs to all pages
- [ ] Implement "you are here" active state styling
- [ ] Create related content suggestions
- [ ] Improve table of contents (sticky? collapsible?)
- [ ] Add anchor links to all headings

### ⚡ Performance Optimization
- [ ] Optimize font loading (subset, preload, font-display: swap)
- [ ] Implement lazy loading for images
- [ ] Minimize CSS bundle size
- [ ] Audit JavaScript usage (can we remove any?)
- [ ] Add service worker for offline support

### 🎯 User Experience Improvements
- [ ] Add smooth scroll behavior
- [ ] Improve loading states (skeleton screens?)
- [ ] Better error pages (404, 500)
- [ ] Add print stylesheet
- [ ] Copy button for code blocks

### 🔍 Content Discovery
- [ ] Enhance search with better ranking
- [ ] Add search keyboard shortcuts (/)
- [ ] Create topic tags/categories
- [ ] Add "Last updated" dates to pages
- [ ] Show estimated reading time

## Low Priority (Delight & Differentiation)

### 💎 Visual Delight
- [ ] Add custom illustrations for key privacy concepts
- [ ] Design custom favicon and social cards
- [ ] Create animated transitions (subtle, purposeful)
- [ ] Add dark mode toggle
- [ ] Personalized microcopy and error messages

### 🎨 Brand Identity
- [ ] Develop privacy-focused color palette (deep blues, warm grays)
- [ ] Choose brand typefaces (IBM Plex Sans/Mono?)
- [ ] Create visual language (shapes, icons, patterns)
- [ ] Design custom diagram style
- [ ] Photography/imagery guidelines (avoid surveillance vibes)

### 🚀 Advanced Features
- [ ] Version switcher for docs
- [ ] Interactive examples (live demos)
- [ ] Feedback widget ("Was this helpful?")
- [ ] Social sharing (respecting privacy)
- [ ] Easter eggs (privacy-themed)

## Completed ✅

_No items completed yet. Start by running the first evaluation!_

---

## Next Actions for Curator

1. **Generate demo:** `uv run egregora demo` (create command if needed)
2. **Serve locally:** `cd demo && uv run mkdocs serve`
3. **Run Lighthouse audit:** Capture baseline scores
4. **Systematic review:** Follow the Curator's inspection workflow
5. **Update this TODO:** Add specific, actionable items based on findings
6. **Create issues:** For high-priority items with screenshots and recommendations

## Reference: Best-in-Class Examples

Compare against these when evaluating:
- **Stripe Docs** (https://stripe.com/docs) - Search, clarity, hierarchy
- **Tailwind CSS** (https://tailwindcss.com/docs) - Visual design, typography
- **Astro Docs** (https://docs.astro.build) - Navigation, personality
- **MDN** (https://developer.mozilla.org) - Information architecture
- **Linear Docs** (https://linear.app/docs) - Minimalist elegance

## Lighthouse Score Tracking

### Baseline (Measure First)
- Performance: ___ / 100
- Accessibility: ___ / 100
- Best Practices: ___ / 100
- SEO: ___ / 100

### Target (Excellence)
- Performance: 95+ / 100
- Accessibility: 100 / 100
- Best Practices: 100 / 100
- SEO: 100 / 100

---

**Note:** This TODO is living documentation. Update it after every Curator session.
Keep it opinionated but evidence-based (screenshots, Lighthouse scores, comparative analysis).

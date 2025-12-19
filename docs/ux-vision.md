# Egregora UX/UI Vision

**Strategic vision for Egregora-generated MkDocs documentation.**

Last updated: 2025-12-19

---

## Vision Statement

Egregora-generated MkDocs blogs should be the **most beautiful, readable, and delightful** documentation in the privacy-first AI space.

Users should feel:
- **Confident** - Professional, trustworthy design
- **Informed** - Clear hierarchy, scannable content
- **Respected** - Accessible, privacy-conscious, no dark patterns

Every design decision should serve the user's need to understand their data and maintain their privacy.

---

## Design Principles

### 1. Privacy-First Visual Identity

**Colors & Imagery:**
- Use colors that evoke **trust and privacy** (deep blues, warm grays, muted tones)
- Avoid surveillance/tracking imagery (no eyeballs, cameras, data harvesting visuals)
- Emphasize **user control** and **transparency** (open locks, clear paths, light)
- Professional but **warm** (not corporate cold, not playful childish)

**Brand Personality:**
- **Thoughtful**, not flashy
- **Empowering**, not patronizing
- **Technical** but accessible
- **Privacy-conscious** but not paranoid

**Example Palette:**
```css
:root {
  /* Primary - Trust & Privacy */
  --color-primary: #1e3a8a;      /* Deep blue */
  --color-primary-light: #3b82f6; /* Bright blue */

  /* Neutral - Warm & Professional */
  --color-text: #1a1a1a;          /* Almost black */
  --color-text-muted: #4b5563;    /* Warm gray */
  --color-background: #ffffff;     /* Pure white */
  --color-background-alt: #f9fafb; /* Off-white */

  /* Accent - Action & Focus */
  --color-accent: #0ea5e9;        /* Sky blue */
  --color-success: #10b981;       /* Green */
  --color-warning: #f59e0b;       /* Amber */
  --color-error: #ef4444;         /* Red */
}
```

### 2. Content First

**Readability Above All:**
- Optimal line length: **45-75 characters** (65ch target)
- High contrast text: **WCAG AAA** (7:1 for body text)
- Generous whitespace: **Breathing room** between elements
- Clear hierarchy: **H1 > H2 > H3** obvious at a glance

**Scannability:**
- Use headings, lists, bold for key terms
- Add table of contents on long pages
- Include anchor links to sections
- Break up walls of text with code blocks, callouts, images

### 3. Accessibility is Non-Negotiable

**WCAG AAA Targets:**
- Color contrast: **7:1** for body text, **4.5:1** for large text
- Keyboard navigation: **Everything** must be keyboard accessible
- Screen readers: **Semantic HTML**, proper ARIA labels
- Focus indicators: **Visible** (blue outline or custom)
- Touch targets: **44px minimum** for mobile

**Inclusive Design:**
- Color is never the **sole** indicator (use icons + color)
- Captions/transcripts for video/audio
- Alt text for all images
- Simple, clear language (Flesch-Kincaid 60+)

### 4. Performance is User Experience

**Lighthouse Targets:**
- Performance: **95+** / 100
- Accessibility: **100** / 100
- Best Practices: **100** / 100
- SEO: **100** / 100

**Optimization Principles:**
- Static HTML preferred (minimal JavaScript)
- Lazy load images below the fold
- Optimize fonts (subset, preload, `font-display: swap`)
- No layout shift (CLS = 0)
- First paint < 1 second

### 5. Mobile-First, Always

**Responsive Design:**
- Design for **320px screens** first, then scale up
- Touch-friendly targets (**44px** minimum)
- No horizontal scroll (ever)
- Readable without zooming
- Adaptive navigation (hamburger on mobile)

**Testing Requirements:**
- Test on actual devices (iOS, Android)
- Test on slow connections (3G throttling)
- Test with touch only (no mouse)

---

## UX/UI Excellence Criteria

### 📖 Content Hierarchy & Readability

**✅ Excellent:**
- Clear visual hierarchy (H1 > H2 > H3 obvious at a glance)
- Optimal line length (45-75 characters for body text)
- Generous whitespace (breathing room between elements)
- Consistent typography scale (harmonious sizes)
- High contrast for body text (WCAG AAA: 7:1 minimum)

**❌ Poor:**
- All headings look the same size
- Lines stretch across entire screen (>100 chars)
- Cramped layouts with minimal spacing
- Random font sizes with no pattern
- Low contrast text (#666 on #888)

### 🎨 Visual Design & Polish

**✅ Excellent:**
- Professional color palette (3-5 colors max, purposeful)
- Consistent spacing system (8px grid or similar)
- Thoughtful use of color (not random highlighting)
- Subtle shadows and depth (not flat, not overdone)
- Custom favicon and branding touches

**❌ Poor:**
- Default MkDocs theme with no customization
- Rainbow of colors with no cohesion
- Inconsistent spacing (5px here, 13px there, 22px elsewhere)
- Harsh shadows or completely flat
- Missing favicon (shows browser default)

### 🧭 Navigation & Information Architecture

**✅ Excellent:**
- Intuitive menu structure (3-7 top-level items)
- Breadcrumbs for deep pages
- Clear "You are here" indicators
- Search that actually works (with good results)
- Related content suggestions

**❌ Poor:**
- Flat menu with 30+ items
- No breadcrumbs (users get lost)
- Can't tell which page you're on
- Search returns irrelevant results
- Dead ends (no next steps)

### ⚡ Performance & Loading

**✅ Excellent:**
- First paint < 1 second
- No layout shift during load
- Lazy-loaded images below fold
- Minimal JavaScript (static HTML preferred)
- Optimized fonts (subset, preload)

**❌ Poor:**
- Blank screen for 3+ seconds
- Content jumps around as it loads
- All images load at once (slow)
- Heavy JavaScript frameworks (unnecessary)
- 10 web fonts from Google (slow)

### 📱 Responsive Design

**✅ Excellent:**
- Mobile-first design (works on 320px screens)
- Touch-friendly targets (44px minimum)
- Readable without zooming
- Hamburger menu on mobile (no horizontal scroll)
- Tables adapt (scroll or stack)

**❌ Poor:**
- Desktop-only (breaks on mobile)
- Tiny tap targets (12px links)
- Must pinch-zoom to read
- Menu overflows off screen
- Tables break layout

### ♿ Accessibility

**✅ Excellent:**
- Semantic HTML (proper heading levels)
- Alt text on all images
- Keyboard navigation works (tab through everything)
- Focus indicators visible (blue outline or better)
- Color not sole indicator (icons + color)

**❌ Poor:**
- Divs and spans instead of semantic tags
- Missing alt text (screen readers confused)
- Can't tab to buttons/links
- Invisible focus (can't see where you are)
- Red/green only (colorblind users lost)

### 🔍 Scannability & Wayfinding

**✅ Excellent:**
- Skimmable content (headings, lists, bold key terms)
- Table of contents on long pages
- Anchor links to sections
- Clear CTAs (what to do next)
- Visual breaks (code blocks, images, callouts)

**❌ Poor:**
- Walls of text (no breaks)
- No TOC on 10-page article
- Can't link to specific section
- No guidance on next steps
- Monotonous content (all paragraphs)

### 💎 Delight & Personality

**✅ Excellent:**
- Custom illustrations or diagrams
- Thoughtful microcopy (friendly, helpful)
- Smooth transitions (not jarring)
- Easter eggs or personality touches
- Memorable visual identity

**❌ Poor:**
- Generic stock photos
- Robotic, corporate tone
- Instant state changes (no transitions)
- Completely sterile (no personality)
- Looks like every other MkDocs site

---

## Best-in-Class Reference Library

When evaluating Egregora's output, compare against these exemplars:

### Information Architecture
- **[Stripe Docs](https://stripe.com/docs)** - Crystal clear hierarchy, excellent search, intuitive navigation
- **[Astro Docs](https://docs.astro.build)** - Great "you are here" indicators, logical structure

### Visual Design
- **[Tailwind CSS](https://tailwindcss.com/docs)** - Beautiful typography and spacing, perfect color palette
- **[Linear Docs](https://linear.app/docs)** - Minimalist elegance, perfect contrast, professional

### Content Quality
- **[Diataxis Framework](https://diataxis.fr)** - Content structure methodology (tutorials, how-to, reference, explanation)
- **[MDN](https://developer.mozilla.org)** - Comprehensive, scannable, authoritative

### Accessibility
- **[GOV.UK Design System](https://design-system.service.gov.uk/)** - WCAG AAA compliance, inclusive design
- **[A11y Project](https://www.a11yproject.com/)** - Accessibility-first approach

### Performance
- **[Jake Archibald's Blog](https://jakearchibald.com/)** - Ultra-fast, progressive enhancement
- **[Astro](https://astro.build)** - Static-first, minimal JS, island architecture

---

## Typography System

**Font Families:**
```css
:root {
  /* Recommended: IBM Plex (open-source, professional, readable) */
  --font-family-sans: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  --font-family-mono: "IBM Plex Mono", "SF Mono", Monaco, monospace;

  /* Alternative: System fonts (fast, no download) */
  --font-family-system: system-ui, -apple-system, BlinkMacSystemFont,
                        "Segoe UI", Roboto, sans-serif;
}
```

**Type Scale (1.25 ratio):**
```css
:root {
  /* Base */
  --text-xs: 0.75rem;   /* 12px */
  --text-sm: 0.875rem;  /* 14px */
  --text-base: 1rem;    /* 16px - mobile base */
  --text-lg: 1.125rem;  /* 18px - desktop base */
  --text-xl: 1.25rem;   /* 20px */
  --text-2xl: 1.563rem; /* 25px */
  --text-3xl: 1.953rem; /* 31px */
  --text-4xl: 2.441rem; /* 39px */
  --text-5xl: 3.052rem; /* 49px */
}

/* Responsive base size */
body {
  font-size: var(--text-base);
  line-height: 1.6;
}

@media (min-width: 768px) {
  body {
    font-size: var(--text-lg);
  }
}
```

**Line Height:**
- Headings: `1.2` (tighter for impact)
- Body text: `1.6` (looser for readability)
- Code: `1.5` (balanced)

**Font Weight:**
- Regular: `400` (body text)
- Medium: `500` (emphasis)
- Semibold: `600` (headings, navigation)
- Bold: `700` (strong emphasis)

---

## Spacing System

**8px Grid:**
```css
:root {
  --space-0: 0;
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-5: 1.25rem;  /* 20px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-10: 2.5rem;  /* 40px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */
  --space-20: 5rem;    /* 80px */
  --space-24: 6rem;    /* 96px */
}
```

**Usage Guidelines:**
- Tight spacing (4-8px): Related elements, list items
- Medium spacing (16-24px): Paragraphs, sections
- Loose spacing (32-48px): Major sections, page breaks
- Extra loose (64px+): Chapter breaks, hero sections

---

## Color Palette

**Primary (Trust & Privacy):**
```css
--blue-50: #eff6ff;
--blue-100: #dbeafe;
--blue-200: #bfdbfe;
--blue-300: #93c5fd;
--blue-400: #60a5fa;
--blue-500: #3b82f6;  /* Primary accent */
--blue-600: #2563eb;
--blue-700: #1d4ed8;
--blue-800: #1e40af;
--blue-900: #1e3a8a;  /* Primary brand */
```

**Neutral (Professional & Warm):**
```css
--gray-50: #f9fafb;
--gray-100: #f3f4f6;
--gray-200: #e5e7eb;
--gray-300: #d1d5db;
--gray-400: #9ca3af;
--gray-500: #6b7280;
--gray-600: #4b5563;
--gray-700: #374151;
--gray-800: #1f2937;
--gray-900: #111827;
```

**Semantic Colors:**
```css
--color-success: #10b981;  /* Green - positive actions */
--color-warning: #f59e0b;  /* Amber - caution */
--color-error: #ef4444;    /* Red - errors, danger */
--color-info: #0ea5e9;     /* Sky blue - information */
```

---

## Common UX Pitfalls to Avoid

### ❌ Pitfall 1: Default Theme Syndrome
**Symptom:** Looks like every other MkDocs site (default blue theme)
**Fix:** Custom color palette, typography, and spacing system

### ❌ Pitfall 2: Desktop-Only Design
**Symptom:** Broken layout on mobile, requires zoom to read
**Fix:** Mobile-first approach, test on 375px viewport

### ❌ Pitfall 3: Wall of Text
**Symptom:** Long pages with no visual breaks or hierarchy
**Fix:** Add headings, lists, callouts, code blocks, images

### ❌ Pitfall 4: Hidden Navigation
**Symptom:** Users can't find what they need, no breadcrumbs
**Fix:** Clear menu structure, breadcrumbs, search, related content

### ❌ Pitfall 5: Low Contrast
**Symptom:** Text is hard to read (#666 on #f0f0f0)
**Fix:** WCAG AA minimum (4.5:1), AAA target (7:1)

### ❌ Pitfall 6: Slow Loading
**Symptom:** 3+ second wait for first paint
**Fix:** Optimize images, fonts, minimize JS, lazy load

### ❌ Pitfall 7: Inaccessible
**Symptom:** Can't use with keyboard, screen reader fails
**Fix:** Semantic HTML, ARIA labels, keyboard nav, focus indicators

---

## Lighthouse Score Targets

### Minimum (Ship Threshold)
- Performance: **90+** / 100
- Accessibility: **95+** / 100
- Best Practices: **95+** / 100
- SEO: **95+** / 100

### Excellence (Target)
- Performance: **95+** / 100
- Accessibility: **100** / 100
- Best Practices: **100** / 100
- SEO: **100** / 100

**Core Web Vitals:**
- LCP (Largest Contentful Paint): **< 2.5s**
- FID (First Input Delay): **< 100ms**
- CLS (Cumulative Layout Shift): **< 0.1**

---

## Implementation Guidelines

### MkDocs Material Theme

**Base Configuration:**
```yaml
# mkdocs.yml
theme:
  name: material
  palette:
    scheme: default
    primary: indigo
    accent: blue
  font:
    text: IBM Plex Sans
    code: IBM Plex Mono
  features:
    - navigation.instant    # SPA-like navigation
    - navigation.tracking   # URL updates as you scroll
    - navigation.tabs       # Top-level sections as tabs
    - navigation.sections   # Section headers in sidebar
    - toc.integrate        # TOC in sidebar
    - search.suggest       # Search suggestions
    - search.highlight     # Highlight search terms
    - content.code.copy    # Copy button for code blocks

extra_css:
  - stylesheets/extra.css
```

**Custom CSS Structure:**
```css
/* docs/stylesheets/extra.css */

/* 1. CSS Variables (Design Tokens) */
:root {
  /* Colors */
  --color-primary: #1e3a8a;
  /* Typography */
  --font-family-sans: "IBM Plex Sans", sans-serif;
  /* Spacing */
  --space-4: 1rem;
  /* ... */
}

/* 2. Base Styles */
body {
  font-size: 16px;
  line-height: 1.6;
  color: var(--color-text);
}

/* 3. Component Overrides */
.md-content {
  max-width: 70ch;
}

/* 4. Responsive */
@media (min-width: 768px) {
  body { font-size: 18px; }
}
```

---

## Related Documents

- **[curator.TODO.md](../curator.TODO.md)** - Tactical task list for UX improvements
- **[.jules/curator.md](../.jules/curator.md)** - Curator persona journal
- **[.jules/forge.md](../.jules/forge.md)** - Forge persona journal
- **[.jules/prompts/curator.md](../.jules/prompts/curator.md)** - Curator persona definition
- **[.jules/prompts/forge.md](../.jules/prompts/forge.md)** - Forge persona definition

---

## Version History

- **2025-12-19** - Initial vision document created
  - Established design principles
  - Defined excellence criteria
  - Set Lighthouse targets
  - Documented best-in-class references

---

**This is a living document.** Update as we learn and evolve our understanding of what makes excellent privacy-focused documentation.

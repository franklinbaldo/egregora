# RFC: Project Chameleon (The Generative UI)
**Status:** Moonshot Proposal
**Date:** 2025-05-28
**Disruption Level:** High (UI/UX Paradigm Shift)

## 1. The Vision
You click on a link to the latest Egregora post titled "The Weekend in Tokyo."
The page loads. It doesn't look like the standard "Corporate Blue" blog template.
The background is a subtle, animated neon rain. The headers use a jagged, brush-stroke font reminiscent of Japanese calligraphy. The layout is a masonry grid, mimicking dense city streets.

You click "Next Post": "Sunday Gardening."
The page transforms. The background is now a soft, textured parchment. The font is a clean, humanist serif. The layout is spacious and breathable.

The website isn't just a container for content; it **is** the content. The interface effectively "hallucinates" a bespoke design system for every single story, matching the *vibe* of the conversation perfectly.

## 2. The Broken Assumption
> "We currently assume that a website's design must be **Consistent** (same header, same font, same colors everywhere), but this prevents us from maximizing **Context**."

Standard web design prioritizes brand consistency. But Egregora isn't a brand; it's a collection of diverse memories. A fight about politics feels different than a photo dump of a puppy. Forcing them into the same visual template flattens the emotional dynamic range.
We treat CSS as a static asset. We should treat CSS as a **Generative Artifact**.

## 3. The Mechanics (High Level)

### Input
*   **The Post Content:** Text, images, and the "Vibe" metadata (Sentiment: Joyful, Topic: Tech, Era: 80s).

### Processing
We introduce the **Design Director Agent**.

1.  **Aesthetic Analysis:**
    *   The LLM analyzes the content not just for summary, but for *Synesthesia*.
    *   "If this chat log was a movie poster, what would it look like?"
    *   Output: A `DesignManifest` JSON (Color Palette, Typography Pairing, Layout Strategy, Texture keywords).

2.  **The CSS Synthesizer:**
    *   We don't write raw CSS. We map the `DesignManifest` to a **Design Token Engine**.
    *   **Colors:** `var(--bg-primary)`, `var(--text-accent)` are generated dynamically.
    *   **Typography:** We integrate with a variable font API (or a curated local set) to select fonts that match the mood (e.g., `font-variation-settings: 'wght' 900, 'slnt' -10` for urgent posts).
    *   **Layout:** The agent selects a Jinja2 Layout Template (e.g., `layouts/editorial.html`, `layouts/terminal.html`, `layouts/gallery.html`).

3.  **Generative Assets:**
    *   The system uses an image generator (Gemini/Imagen) to create subtle, tiled background patterns or header textures based on the manifest.

### Output
*   **Artifact:** A `theme.css` generated specifically for *that specific permalink*.
*   **Mechanism:** The `<head>` of the page links to the global style, but then includes an inline `<style>` block or a specific CSS file that overrides the CSS variables for the `<body>` scope.

## 4. The Value Proposition
*   **Immersion:** It turns reading a log into an *experience*. It honors the content by dressing it appropriately.
*   **differentiation:** No other blogging platform does this. It is the antithesis of the "Substack Grey" homogenization of the web.
*   **Emotional Impact:** The user *feels* the mood of the conversation before they read a single word.

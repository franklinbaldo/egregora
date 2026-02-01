# User Interface & Experience (UI/UX)

> **Theme:** Portal Theme
> **Status:** Active
> **Primary Maintainer:** Forge (⚒️)

The **Portal Theme** is the custom design system for the Egregora documentation site. It is built on top of [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) but applies significant overrides to create a distinct, "magical" yet professional aesthetic.

## 🎨 Design Philosophy

The Portal Theme is designed to be:
1.  **Immersive**: Using a full-width "Hero" section on the homepage to draw users into the world of the system.
2.  **Clean & Readable**: Prioritizing high-contrast typography and optimal line lengths (approx 75 characters) for long-form reading.
3.  **Glassmorphic**: Utilizing subtle transparency and borders to create depth without clutter.

## 🛠️ Technical Implementation

The theme is implemented via a single consolidated CSS file:
`src/egregora/rendering/templates/site/overrides/stylesheets/extra.css`

This file overrides the default MkDocs Material styles using high-specificity selectors.

### Scoping Strategy
To prevent styles from "leaking" where they shouldn't (e.g., breaking the navigation bar), we use scoped selectors:
- **Homepage Specific**: `.md-main__inner:has(.homepage-hero)` targets only the homepage layout.
- **Component Specific**: Classes like `.md-post--card` and `.admonition.glass` isolate component styles.

### Dark Mode Support
The theme natively supports the "Slate" color scheme.
- **Selector**: `[data-md-color-scheme="slate"]`
- **Behavior**: Automatically adjusts background colors, border contrasts, and text readability when the user toggles dark mode.

## 🧩 Key Components

### 1. The Homepage Hero
A full-viewport height section that serves as the entry point.
- **Class**: `.homepage-hero`
- **Features**: Gradient background, centered typography, responsive design.

### 2. Card Design
Used for blog posts and feature highlights.
- **Class**: `.md-post--card`
- **Style**: White/Dark background with a subtle border (`#e0e0e0`) and shadow.
- **Interaction**: Slight lift (`translateY(-2px)`) and shadow increase on hover.

### 3. Related Posts Grid
A 3-column grid at the bottom of posts to encourage exploration.
- **Class**: `.related-posts-grid`
- **Layout**: CSS Grid with `minmax(250px, 1fr)` for responsiveness.

### 4. Media Gallery
A specialized layout for displaying enriched media links.
- **Class**: `.media-gallery`
- **Features**: Truncated URLs, hover effects, and distinct "card" presentation for external links.

## typography

- **Font Family**: Uses the `Inter` font family (theme default) with a system font fallback for performance.
- **Readability**: Base font size is increased to `1.1rem` for better legibility on modern screens.

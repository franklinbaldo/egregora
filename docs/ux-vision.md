# 🎭 Curator's UX Vision for Egregora

This document outlines the user experience (UX) and design principles for Egregora-generated MkDocs blogs. It is a living document maintained by the Curator persona, intended to guide the evolution of the blog's design system.

## Core Principles

1.  **Readability First**: The primary goal is to create a comfortable and engaging reading experience. All design choices must prioritize text clarity, optimal line length, and generous whitespace.
2.  **Autonomously Generated**: The design must be achievable through 100% autonomous generation. Features that require manual human input are not considered.
3.  **Distinctive Identity**: The blog should have a unique and memorable visual identity that reflects the "collective consciousness" theme of Egregora.
4.  **Accessible by Default**: All components and styles must meet WCAG AA standards at a minimum, with a stretch goal for AAA where feasible.
5.  **Performant & Lightweight**: The site should be fast and responsive, with minimal JavaScript and optimized assets.

## Design System

### Color Palette

The color palette is designed to be distinctive and professional, moving away from the default Material for MkDocs theme. It evokes a sense of thoughtful introspection and energetic connection.

-   **Primary Color**: `indigo`
    -   **Rationale**: Represents depth, thought, and knowledge. It's a strong, professional color that works well for headers and primary actions.
-   **Accent Color**: `orange`
    -   **Rationale**: Represents energy, creativity, and connection. It provides a warm, vibrant contrast to the primary color, ideal for links and highlights.

| Element       | Light Mode | Dark Mode  |
| :------------ | :--------- | :--------- |
| **Primary**   | `indigo`   | `indigo`   |
| **Accent**    | `orange`   | `orange`   |

### Typography

-   **Body Text**: `Roboto`
    -   **Rationale**: A clean, modern, and highly readable sans-serif font suitable for long-form content.
-   **Code Blocks**: `Roboto Mono`
    -   **Rationale**: A monospaced variant that provides excellent clarity for code snippets.

### Spacing & Layout

-   **Line Length**: `45rem` (approximately 65-75 characters)
    -   **Rationale**: The optimal line length for reading comfort, reducing eye strain during long reading sessions.
-   **Base Font Size**: `1.1rem`
    -   **Rationale**: A slightly larger base font size to improve readability on modern high-resolution screens.

## Template Architecture

-   **Source of Truth**: The templates for the MkDocs site are not stored as standalone `.jinja2` or `.html` files. Instead, they are managed within the Egregora Python source code.
-   **Key Files**:
    -   `src/egregora/output_adapters/mkdocs/scaffolding.py`: Handles the initial creation of the site structure, including `mkdocs.yml` and other configuration files.
    -   `src/egregora/output_adapters/mkdocs/adapter.py`: Responsible for generating the individual Markdown pages for posts, profiles, and other content.
    -   `src/egregora/rendering/templates/site/`: This directory contains the source Jinja templates and static assets (like `extra.css`) that are copied into new sites during scaffolding.

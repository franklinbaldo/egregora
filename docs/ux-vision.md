# 🎭 Curator's UX Vision for Egregora

This document outlines the evolving vision for the user experience of Egregora-generated MkDocs blogs. It is maintained by the Curator persona and serves as a guiding star for UX/UI improvements.

## Guiding Principles

1.  **Content-First**: The design must elevate the written content, not distract from it. Readability, clarity, and focus are paramount.
2.  **Autonomously Generated**: All UX features must be derivable from the data itself. We will never require human intervention to populate or complete a feature.
3.  **Privacy-Preserving**: The UX will respect user privacy by default. Features like analytics will be opt-in or removed entirely.
4.  **Aesthetically Pleasing**: The blog should be visually appealing and professional, reflecting the "collective consciousness" theme of Egregora.

## Template Architecture

A critical discovery is that the MkDocs templates are **not** stored in separate `.jinja2` or `.html` files. Instead, they are embedded within the Python source code of the MkDocs output adapter.

- **Primary Source Files**:
    - `src/egregora/output_adapters/mkdocs/adapter.py`: Handles the generation of individual Markdown pages.
    - `src/egregora/output_adapters/mkdocs/scaffolding.py`: Generates the `mkdocs.yml` file and the initial site structure.
    - `src/egregora/output_adapters/mkdocs/site_generator.py`: Orchestrates the overall site generation and supplemental pages.

- **Implications**:
    - All UX/UI changes that require template modifications must be made in these Python files.
    - The "Forge" persona will need to be comfortable editing these embedded templates.
    - This architecture keeps the templating logic tightly coupled with the generation logic, which can be both a strength and a weakness. We will monitor this as the project evolves.

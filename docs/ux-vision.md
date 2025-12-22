# UX Vision

This document outlines the user experience (UX) vision for the generated blogs.

## Template Architecture

The MkDocs templates are located in the following directory:

`src/egregora/rendering/templates/site/`

This directory contains the Jinja2 templates for `mkdocs.yml`, theme overrides, and content pages. All frontend changes should be made to these templates.

## Core Readability

A primary goal of the UX vision is to ensure all generated blogs are highly readable, especially for long-form content. This is achieved through two key principles:

1.  **Optimal Font Size**: The base font size for body content should be `1.1rem` (approximately 18px). This is slightly larger than the default for most browsers and themes, providing a more comfortable reading experience and reducing eye strain.

2.  **Optimal Line Length**: The main content width will be capped at a maximum of `75ch`. This ensures that lines of text do not become excessively long on wide screens, which can make it difficult for the reader's eye to track from one line to the next. This range is widely accepted as the optimal line length for readability.

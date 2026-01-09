---
id: 20260109-2027-ux-improve-color-palette
title: "🎭 Design and Implement a Custom Color Palette"
tags:
  - ux
  - frontend
  - design
  - high-priority
persona: forge
status: todo
---

## 1. Why is this important?

The current blog uses the default "teal" and "amber" color palette from the Material for MkDocs theme. While functional, it looks generic and fails to establish a unique brand identity for Egregora, which is positioned as a "collective consciousness" tool. A custom, professional color palette will significantly improve the site's aesthetic appeal, memorability, and perceived quality.

## 2. What needs to be done?

The `forge` persona needs to implement a new, custom color palette. As the `curator`, I have designed a palette that reflects the project's identity:

- **Primary:** A deep, thoughtful blue (`#2c3e50`) to represent intellect and depth.
- **Accent:** A vibrant, energetic green (`#27ae60`) to represent emergence and growth.

### Implementation Steps:

1.  **Locate the configuration file:** The color palette is defined in the `mkdocs.yml` file. The source template for this is located in `src/egregora/output_adapters/mkdocs/scaffolding.py`.
2.  **Modify the Jinja template:** Find the `theme.palette` section within the `MKDOCS_YML_TEMPLATE` string in `scaffolding.py`.
3.  **Update the colors:**
    -   Change `primary: teal` to `primary: custom`.
    -   Change `accent: amber` to `accent: green`.
4.  **Define the custom color:** Add the primary color override to the `extra.css` template. The source for this is also in `scaffolding.py` within the `EXTRA_CSS_TEMPLATE` string. Add the following CSS:

    ```css
    :root {
      --md-primary-fg-color:        #2c3e50;
      --md-primary-fg-color--light: #34495e;
      --md-primary-fg-color--dark:  #2c3e50;
    }
    ```

## 3. How do I verify it's done?

1.  Run `uv run egregora demo` to regenerate the demo site.
2.  Inspect the generated `demo/.egregora/mkdocs.yml` file. Verify that `primary` is set to `custom` and `accent` is set to `green`.
3.  Inspect the generated `demo/docs/stylesheets/extra.css` file. Verify that the `:root` definition with the custom primary color variables exists.
4.  **Visual Verification:** Build and serve the site (`cd demo && uv run mkdocs build -f .egregora/mkdocs.yml` then serve the `site` directory). The primary color of the header and links should now be the deep blue (`#2c3e50`).

This change will provide a more professional and branded look to the generated blogs.

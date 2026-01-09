---
id: 20260109-2028-ux-remove-analytics
title: "🎭 Remove Placeholder Google Analytics"
tags:
  - ux
  - privacy
  - high-priority
persona: forge
status: todo
---

## 1. Why is this important?

The `mkdocs.yml` configuration currently includes a Google Analytics property with a placeholder value (`__GOOGLE_ANALYTICS_KEY__`). This is problematic for two reasons:

1.  **Broken Feature:** As a placeholder, the feature is non-functional.
2.  **Privacy Misalignment:** Egregora promotes itself as a "privacy-first" tool. Including an analytics tracker, even as a placeholder, contradicts this core principle. It's better to remove it entirely and let users add it back *explicitly* if they choose, rather than including it by default.

## 2. What needs to be done?

The `forge` persona needs to remove the entire `extra.analytics` section from the `mkdocs.yml` template.

### Implementation Steps:

1.  **Locate the configuration template:** The template is the `MKDOCS_YML_TEMPLATE` string in `src/egregora/output_adapters/mkdocs/scaffolding.py`.
2.  **Remove the analytics block:** Find and delete the entire `extra.analytics` section from the Jinja template. The block to be removed looks like this:

    ```yaml
    extra:
      analytics:
        provider: google
        property: "__GOOGLE_ANALYTICS_KEY__"
        feedback:
          title: Was this page helpful?
          ratings:
            - icon: material/emoticon-happy-outline
              name: This page was helpful
              data: 1
              note: >-
                Thanks for your feedback!
            - icon: material/emoticon-sad-outline
              name: This page could be improved
              data: 0
              note: >-
                Thanks for your feedback! Help us improve this page by
                <a href="/issues/new?title=[Docs]" target="_blank">opening an issue</a>.
    ```
    *Note: Be careful to only remove the `analytics` key and its children from the `extra` section, not the entire `extra` section itself.*

## 3. How do I verify it's done?

1.  Run `uv run egregora demo` to regenerate the demo site.
2.  Inspect the generated `demo/.egregora/mkdocs.yml` file. Verify that the `extra.analytics` section has been completely removed.
3.  Build the site (`cd demo && uv run mkdocs build -f .egregora/mkdocs.yml`) and inspect the generated `site/index.html`. There should be no Google Analytics scripts included in the HTML source.

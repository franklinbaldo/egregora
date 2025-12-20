## 2025-06-15 - Curator's Journal: Initializing the Vision

**Observation:** This is my first run as Curator. I've been tasked with establishing and evolving the UX vision for Egregora-generated blogs. The initial documentation (`docs/ux-vision.md`, `TODO.ux.toml`) provides a strong, structured starting point.

**Why It Matters:** A clear journal is essential for tracking my autonomous decisions, learnings, and the reasoning behind them. This ensures my work is transparent and builds a long-term, coherent vision.

**First Steps & Discoveries:**
1.  **Template Discovery:** Successfully located the MkDocs templates at `src/egregora/rendering/templates/site/`. This was the critical first step. The presence of `mkdocs.yml.jinja` and theme `overrides/` confirms this is the correct location. I will document this in the main vision file.
2.  **Initial Documentation Review:** The vision and TODO files are well-structured. The `TODO.ux.toml` is particularly detailed, which gives me a clear set of initial evaluation criteria to audit against. The task `find-templates` is already complete.
3.  **Next Actions:** My immediate plan is to generate the demo site, perform a baseline Lighthouse audit as per the `baseline-lighthouse` task, and then create my first set of new, actionable tasks based on that initial, data-driven inspection.

## 2025-06-16 - UX Inspection: Critical Failures in Generation

**Observation:** The initial demo generation process is fundamentally broken, preventing any meaningful UX/UI evaluation. The out-of-the-box experience is completely non-functional.

**Why It Matters:** A user's first impression is critical. If the tool fails to produce a working, populated blog from its own sample data, it immediately loses all credibility and creates a frustrating, negative experience. It's the most severe UX failure possible: the product does not do what it claims to do.

**Key Issues Discovered:**
1.  **Empty Blog Generation:** The `egregora write` command completes without error but generates **zero posts**. The resulting blog is an empty shell. This is a complete failure of the core value proposition.
2.  **Broken Scaffolding:** The `egregora init` command produces a broken configuration. The `mkdocs serve` command fails due to a missing `overrides` directory and multiple undeclared plugin dependencies (`mkdocs-macros-plugin`, `mkdocs-glightbox`, etc.). This requires the user to manually debug the scaffolding process.
3.  **Incorrect Homepage:** The default homepage is technical documentation for Egregora, not the user's generated blog. This is a confusing default that is not aligned with the user's primary goal of viewing their own content.

**Recommendation:** I have created three high-priority tasks in `TODO.ux.toml` to address these blocking issues. All other UX improvements are secondary until a user can successfully generate a populated, working blog on their first try. The immediate focus must be on fixing this broken core experience.
## ✍️ 2026-01-16 - Standardized Preview Command

**Observation:** I noticed that the command for previewing the documentation site was inconsistent across `README.md`, `docs/getting-started/quickstart.md`, and `docs/getting-started/installation.md`. The command in `README.md` relied on having the repository checked out, which is not true for end-users. Additionally, the commands included `mkdocs-blogging-plugin`, which I verified is redundant because the user site uses the built-in blog plugin from MkDocs Material.

**Action:** I standardized the preview command in all three files to a standalone `uv tool run` command that explicitly lists only the necessary plugins found in the user site template:
`uv tool run --with mkdocs-material --with mkdocs-macros-plugin --with mkdocs-rss-plugin --with mkdocs-glightbox --with mkdocs-git-revision-date-localized-plugin --with mkdocs-minify-plugin mkdocs serve -f .egregora/mkdocs.yml`

**Reflection:** This change ensures that the documentation is accurate and copy-paste-runnable for new users, eliminating potential confusion and installation errors. Future work should focus on automating the verification of documentation commands to prevent regression.

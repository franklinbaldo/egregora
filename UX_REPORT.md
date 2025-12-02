# UX Report: Egregora CLI

## Executive Summary
Egregora's CLI provides a straightforward workflow for converting chat logs into a blog, but suffers from inconsistencies between commands (`write` vs `read`) and minor usability friction (confusing flags, environment variable handling). The output quality is high, but privacy defaults may confuse users (UUIDs as names).

## Critical Findings

### 1. Broken "Read" Workflow (Path Inconsistency)
- **Issue:** The `egregora write` command generates posts in `OUTPUT_DIR/docs/posts` (standard MkDocs structure), but `egregora read` expects them in `OUTPUT_DIR/posts`.
- **Impact:** The `read` command fails out-of-the-box with `Posts directory not found`.
- **Recommendation:** Update `read` command to respect `docs_dir` configuration or unify path resolution logic with `write`.

### 2. Environment Variable Confusion
- **Issue:** The application strictly requires `GOOGLE_API_KEY`. While `GEMINI_API_KEY` is present in the environment (and arguably more specific), it is ignored, leading to a crash.
- **Impact:** Users with valid Gemini keys fail to run the tool unless they alias the variable.
- **Recommendation:** Automatically fallback to `GEMINI_API_KEY` if `GOOGLE_API_KEY` is missing, or explicitly check both.

### 3. "Not Empty" Warning on Valid Sites
- **Issue:** Running `egregora write` on a directory previously initialized with `egregora init` triggers a warning: "The output directory is not empty... Initialize a fresh site here?".
- **Impact:** Confuses users who followed the recommended `init` -> `write` workflow.
- **Recommendation:** Check for a valid `.egregora/config.yml` and suppress the warning if the directory is already a valid Egregora site.

## Usability Improvements

### 4. CLI Flag Inconsistencies
- **Issue:** `init` uses a positional argument for output (`egregora init OUT_DIR`), while `write` uses a flag (`--output-dir`), and users often guess `--output`.
- **Recommendation:** Alias `--output` to `--output-dir` in `write`. Consider allowing a positional argument for `write` output if input file is specified.

### 5. Hidden `mkdocs.yml`
- **Issue:** `mkdocs.yml` is placed in `.egregora/mkdocs.yml`. Running standard `mkdocs serve` or `mkdocs build` fails unless the user knows to pass `-f .egregora/mkdocs.yml`.
- **Recommendation:** Create a symlink `mkdocs.yml -> .egregora/mkdocs.yml` in the site root during initialization, or provide a wrapper command `egregora serve` that handles this.

### 6. Privacy/UX Trade-off (UUIDs)
- **Issue:** Default privacy settings replace author names with UUIDs in the generated profile metadata and UI. This looks broken (e.g., Title: `23e57074...`).
- **Recommendation:** Default to generating fun pseudonyms (e.g., "Anonymous Armadillo") or "User A" instead of raw UUIDs, or ensure the UI renders a fallback label.

## Performance & Reliability
- **Observation:** Ingestion of a 200MB zip file was handled robustly.
- **Observation:** `gdown` was required for Google Drive links; the tool does not handle them natively. This is acceptable but could be documented.

# User Stories Resolved by MkDocs Media Fixes

## 1. MkDocs Sites with Custom `docs_dir`
- **As** a site maintainer who stores MkDocs content outside the default `docs/` folder
- **I want** Egregora to honor whatever `docs_dir` is set to so assets land under the actual site root
- **So that** media, posts, and enrichments appear where MkDocs expects them without manual moves.

## 2. Media as First-Class Documents
- **As** a developer debugging generated content
- **I want** every extracted media asset represented as an Egregora `Document` with deterministic IDs
- **So that** enrichments can link to parents, and tooling (RAG, adapters) can reason about media uniformly.

## 3. Enrichment Markdown Stored Beside Its Media
- **As** an editor reviewing auto-generated captions
- **I want** enrichment `.md` files to live next to their parent media files (same path, different extension)
- **So that** it is obvious which description belongs to which image/video without scanning multiple folders.

## 4. UrlConvention Controls Public Paths
- **As** someone deploying MkDocs to GitHub Pages
- **I want** canonical URLs to be derived from the configured `docs_dir` rather than hard-coded `docs/media`
- **So that** the published site uses stable, predictable permalinks that match the final directory layout.

## 5. Enrichment Agents Don’t Deal with File Paths
- **As** a contributor refactoring the enrichment pipeline
- **I want** the agents to operate purely on `Document` metadata instead of raw filesystem paths
- **So that** adapters handle all IO concerns and we can eventually share enrichment logic across output formats.

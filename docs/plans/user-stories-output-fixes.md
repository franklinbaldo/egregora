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

## 6. LLMs Provide Human-Friendly Slugs
- **As** a reviewer linking to generated assets
- **I want** the writer and enrichment agents to emit descriptive slugs (not UUID fragments)
- **So that** canonical URLs communicate the subject of posts, media, and enrichments and can be referenced verbally.

## 7. Blog Landing Page Explains Itself
- **As** a first-time visitor to the generated site
- **I want** the home page to highlight what the project does and how to navigate it
- **So that** I don’t have to guess which tab contains posts, profiles, media, or operational logs.

## 8. Posts Index with Filters and Tags
- **As** a reader skimming dozens of AI-generated essays
- **I want** the `/posts/` index to expose search, tag, and contributor filters plus a real listing
- **So that** I can quickly home in on the topics or voices I care about without scrolling 1,000 links.

## 9. Media Library as Documentation, Not a Dump
- **As** a curator auditing safety/privacy issues
- **I want** the media section to explain how files and enrichments are organized and link back to posts
- **So that** I can validate assets without spelunking raw directories.

## 10. Journals Carry Accurate Metadata
- **As** someone ingesting the RSS feed or reviewing past runs
- **I want** journal pages to include ISO timestamps and nav hints
- **So that** time-based tooling (RSS, mkdocs-rss-plugin) can parse entries and keep them out of the sidebar clutter.

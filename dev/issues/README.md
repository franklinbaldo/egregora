# Egregora Development Issues

This directory contains detailed issue documentation for Egregora improvements based on real-world testing and analysis.

## GitHub Synchronization

All files in this folder are automatically synchronized with GitHub Issues. A
GitHub Actions workflow runs hourly, on every change to `dev/issues`, and in
response to issue updates on GitHub to keep both sides aligned. Each Markdown
file contains a short HTML comment block at the top where the synchronization
metadata (linked GitHub issue number, state, last sync timestamp, and a content
hash) is stored—please leave this block intact.

To sync manually you can run `python scripts/issue_sync.py` locally (provide
`GITHUB_TOKEN`/`GITHUB_REPOSITORY` if not running inside GitHub Actions). Any
edits to the Markdown body will be reflected in the matching GitHub issue, and
updates performed directly on GitHub will be mirrored back into the
corresponding Markdown file.

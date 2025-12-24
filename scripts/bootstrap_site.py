#!/usr/bin/env python3
"""Ensure an MkDocs site scaffolding exists inside a cloned repository."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from egregora.output_adapters.mkdocs.scaffolding import ensure_mkdocs_project


def main() -> None:
    parser = ArgumentParser(
        description="Bootstrap the .egregora directory and mkdocs.yml for the given site root."
    )
    parser.add_argument(
        "site_root",
        nargs="?",
        default=".",
        help="Filesystem path to the site root (defaults to current directory).",
    )
    parser.add_argument(
        "--site-name",
        "--name",
        dest="site_name",
        help="Optional site name used when initializing MkDocs scaffolding.",
    )

    args = parser.parse_args()
    site_root = Path(args.site_root).expanduser().resolve()
    site_root.mkdir(parents=True, exist_ok=True)

    docs_dir, created = ensure_mkdocs_project(site_root, site_name=args.site_name)

    if created:
        status = "created"
    else:
        status = "verified"

    print(f"{status.capitalize()} MkDocs scaffolding at {site_root} (docs: {docs_dir}).")


if __name__ == "__main__":
    main()

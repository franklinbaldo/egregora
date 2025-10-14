"""Core logic for building the MkDocs static site."""

from __future__ import annotations

from pathlib import Path
import subprocess
import yaml
import shutil

from ..config import PipelineConfig


class StaticSiteBuilder:
    """Builds the MkDocs static site."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.mkdocs_config_path = self.config.posts_dir / "mkdocs.yml"

    def generate_mkdocs_config(self):
        """Generates the mkdocs.yml file."""
        docs_dir = self.config.posts_dir / "docs"
        posts_dir = docs_dir / "posts"
        nav = [{"Home": "index.md"}]
        posts = []
        for post in sorted(posts_dir.glob("*.md"), reverse=True):
            posts.append({post.stem: post.relative_to(docs_dir).as_posix()})
        if posts:
            nav.append({"Posts": posts})

        mkdocs_config = {
            "site_name": "Egregora",
            "theme": "material",
            "nav": nav,
        }
        with open(self.mkdocs_config_path, "w") as f:
            yaml.dump(mkdocs_config, f)

    def prepare_docs(self):
        """Copies posts and generates the index."""
        docs_dir = self.config.posts_dir / "docs"
        posts_dir = docs_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        # Copy posts
        for post in self.config.posts_dir.glob("*.md"):
            shutil.copy(post, posts_dir)

        # Generate index
        index_content = "# Home\n\n"
        for post in sorted(posts_dir.glob("*.md"), reverse=True):
            index_content += f"- [{post.stem}]({post.relative_to(docs_dir).as_posix()})\n"
        (docs_dir / "index.md").write_text(index_content)

    def build(self):
        """Builds the static site."""
        self.prepare_docs()
        self.generate_mkdocs_config()
        subprocess.run(["mkdocs", "build", "-f", str(self.mkdocs_config_path)])

    def serve(self):
        """Serves the static site."""
        self.prepare_docs()
        self.generate_mkdocs_config()
        subprocess.run(["mkdocs", "serve", "-a", "0.0.0.0:8001", "-f", str(self.mkdocs_config_path)])

"""Hugo output format implementation (TEMPLATE/EXAMPLE).

This is a template showing how to implement a new output format.
To complete this implementation, you would need to:
1. Install Hugo: https://gohugo.io/installation/
2. Choose a Hugo theme
3. Implement the scaffolding and post writing logic

This template demonstrates the interface that needs to be implemented.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..core.output_format import OutputFormat, SiteConfiguration

logger = logging.getLogger(__name__)


class HugoOutputFormat(OutputFormat):
    """Hugo static site generator output format.

    Hugo uses:
    - TOML/YAML front matter for metadata
    - Content organized in content/ directory
    - Themes for styling
    - Fast build times

    Note: This is a template implementation. To use it, you need to:
    1. Install Hugo
    2. Choose and configure a theme
    3. Complete the implementation below
    """

    @property
    def format_type(self) -> str:
        """Return 'hugo' as the format type identifier."""
        return "hugo"

    def supports_site(self, site_root: Path) -> bool:
        """Check if the site root is a Hugo site.

        Args:
            site_root: Path to check

        Returns:
            True if config.toml or hugo.toml exists
        """
        if not site_root.exists():
            return False

        # Hugo config can be config.toml, hugo.toml, or config.yaml
        config_files = ["config.toml", "hugo.toml", "config.yaml", "hugo.yaml"]
        return any((site_root / f).exists() for f in config_files)

    def scaffold_site(
        self, site_root: Path, site_name: str, theme: str = "PaperMod", **kwargs
    ) -> tuple[Path, bool]:
        """Create the initial Hugo site structure.

        Args:
            site_root: Root directory for the site
            site_name: Display name for the site
            theme: Hugo theme to use (default: PaperMod)
            **kwargs: Additional options

        Returns:
            tuple of (config_file_path, was_created)

        Raises:
            RuntimeError: If scaffolding fails
            NotImplementedError: This is a template - full implementation needed
        """
        site_root = site_root.expanduser().resolve()
        site_root.mkdir(parents=True, exist_ok=True)

        config_file = site_root / "config.toml"

        if config_file.exists():
            logger.info(f"Hugo site already exists at {site_root}")
            return config_file, False

        # Create Hugo directory structure
        # TODO: Use `hugo new site` command or create manually
        # Directory structure:
        # site_root/
        #   ├── config.toml
        #   ├── content/
        #   │   ├── posts/
        #   │   └── profiles/
        #   ├── static/
        #   │   └── media/
        #   ├── themes/
        #   └── layouts/

        # Create directories
        (site_root / "content" / "posts").mkdir(parents=True, exist_ok=True)
        (site_root / "content" / "profiles").mkdir(parents=True, exist_ok=True)
        (site_root / "static" / "media").mkdir(parents=True, exist_ok=True)
        (site_root / "themes").mkdir(parents=True, exist_ok=True)
        (site_root / "layouts").mkdir(parents=True, exist_ok=True)

        # Create config.toml
        config_content = f"""baseURL = "http://localhost:1313/"
languageCode = "en-us"
title = "{site_name}"
theme = "{theme}"

[params]
  description = "Automated conversation archive"
  author = "Egregora"

[[menu.main]]
  name = "Posts"
  url = "/posts/"
  weight = 1

[[menu.main]]
  name = "Profiles"
  url = "/profiles/"
  weight = 2
"""

        config_file.write_text(config_content, encoding="utf-8")

        logger.info(f"Created Hugo site at {site_root}")
        logger.warning(f"Remember to install the {theme} theme or choose another theme!")

        return config_file, True

    def resolve_paths(self, site_root: Path) -> SiteConfiguration:
        """Resolve all paths for an existing Hugo site.

        Args:
            site_root: Root directory of the site

        Returns:
            SiteConfiguration with all resolved paths

        Raises:
            ValueError: If site_root is not a valid Hugo site
        """
        if not self.supports_site(site_root):
            raise ValueError(f"{site_root} is not a valid Hugo site")

        # Find config file
        config_file = None
        for filename in ["config.toml", "hugo.toml", "config.yaml", "hugo.yaml"]:
            candidate = site_root / filename
            if candidate.exists():
                config_file = candidate
                break

        # Hugo uses content/ directory
        content_dir = site_root / "content"
        posts_dir = content_dir / "posts"
        profiles_dir = content_dir / "profiles"
        media_dir = site_root / "static" / "media"

        return SiteConfiguration(
            site_root=site_root,
            site_name="Hugo Site",  # TODO: Parse from config
            docs_dir=content_dir,
            posts_dir=posts_dir,
            profiles_dir=profiles_dir,
            media_dir=media_dir,
            config_file=config_file,
        )

    def write_post(
        self,
        content: str,
        metadata: dict[str, Any],
        output_dir: Path,
        **kwargs,
    ) -> str:
        """Write a blog post in Hugo format.

        Args:
            content: Markdown content of the post
            metadata: Post metadata (title, date, slug, tags, authors, etc.)
            output_dir: Directory to write the post to
            **kwargs: Additional options

        Returns:
            Path to the written file (as string)

        Raises:
            ValueError: If required metadata is missing
        """
        required = ["title", "slug", "date"]
        for key in required:
            if key not in metadata:
                raise ValueError(f"Missing required metadata: {key}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Hugo filename format: slug.md or YYYY-MM-DD-slug.md
        slug = metadata["slug"]
        date_str = metadata["date"]
        filename = f"{date_str}-{slug}.md"
        filepath = output_dir / filename

        # Build Hugo front matter (TOML format)
        # Alternatively, could use YAML with --- delimiters
        front_matter = f"""+++
title = "{metadata["title"]}"
date = {date_str}
draft = false
"""

        if "tags" in metadata:
            tags = ", ".join(f'"{t}"' for t in metadata["tags"])
            front_matter += f"tags = [{tags}]\n"

        if "summary" in metadata:
            summary = metadata["summary"].replace('"', '\\"')
            front_matter += f'description = "{summary}"\n'

        if "authors" in metadata:
            authors = ", ".join(f'"{a}"' for a in metadata["authors"])
            front_matter += f"authors = [{authors}]\n"

        front_matter += "+++\n\n"

        # Write post
        full_post = front_matter + content
        filepath.write_text(full_post, encoding="utf-8")

        logger.info(f"Wrote Hugo post to {filepath}")
        return str(filepath)

    def write_profile(
        self,
        author_id: str,
        profile_data: dict[str, Any],
        profiles_dir: Path,
        **kwargs,
    ) -> str:
        """Write an author profile page in Hugo format.

        Args:
            author_id: Unique identifier for the author
            profile_data: Profile information
            profiles_dir: Directory to write the profile to
            **kwargs: Additional options

        Returns:
            Path to the written file (as string)
        """
        if not author_id:
            raise ValueError("author_id cannot be empty")

        profiles_dir.mkdir(parents=True, exist_ok=True)

        # Extract content
        if isinstance(profile_data, str):
            content = profile_data
            title = author_id
        else:
            content = profile_data.get("content", "")
            title = profile_data.get("name", author_id)

        # Hugo front matter
        front_matter = f"""+++
title = "{title}"
type = "profile"
+++

"""

        # Write profile
        filepath = profiles_dir / f"{author_id}.md"
        filepath.write_text(front_matter + content, encoding="utf-8")

        logger.info(f"Wrote Hugo profile to {filepath}")
        return str(filepath)

    def load_config(self, site_root: Path) -> dict[str, Any]:
        """Load Hugo site configuration.

        Args:
            site_root: Root directory of the site

        Returns:
            Dictionary of configuration values

        Raises:
            FileNotFoundError: If config file doesn't exist
            NotImplementedError: TOML parsing needed
        """
        # Find config file
        for filename in ["config.toml", "hugo.toml"]:
            config_file = site_root / filename
            if config_file.exists():
                # TODO: Parse TOML config
                # import tomli or toml
                # with config_file.open("rb") as f:
                #     return tomli.load(f)
                logger.warning("Hugo config parsing not fully implemented")
                return {"site_name": "Hugo Site"}

        raise FileNotFoundError(f"No Hugo config file found in {site_root}")

    def get_markdown_extensions(self) -> list[str]:
        """Get list of supported markdown extensions for Hugo.

        Returns:
            List of markdown extension identifiers
        """
        return [
            "tables",
            "fenced_code",
            "footnotes",
            "definition_lists",
            "strikethrough",
            "task_lists",
            # Hugo uses Goldmark by default which supports:
            "autolink",
            "typographer",
        ]

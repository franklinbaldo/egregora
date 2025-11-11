"""Site scaffolding utilities for MkDocs-based Egregora sites."""

import logging
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError, select_autoescape

from egregora.config import SitePaths
from egregora.config.loader import create_default_config
from egregora.config.site import _ConfigLoader, resolve_site_paths

logger = logging.getLogger(__name__)
SITE_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "rendering" / "templates" / "site"
DEFAULT_SITE_NAME = "Egregora Archive"
DEFAULT_DOCS_SETTING = "docs"


def ensure_mkdocs_project(site_root: Path) -> tuple[Path, bool]:
    """Ensure site_root contains an MkDocs configuration.

    Returns the directory where documentation content should be written and a flag
    indicating whether the configuration was created during this call.
    """
    site_root = site_root.expanduser().resolve()
    site_root.mkdir(parents=True, exist_ok=True)
    mkdocs_path = site_root / "mkdocs.yml"
    created = False
    if mkdocs_path.exists():
        docs_dir = _read_existing_mkdocs(mkdocs_path, site_root)
    else:
        docs_dir = _create_default_mkdocs(mkdocs_path, site_root)
        created = True
    docs_dir.mkdir(parents=True, exist_ok=True)
    return (docs_dir, created)


def _read_existing_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Return the docs directory defined by an existing mkdocs.yml."""
    try:
        payload = yaml.load(mkdocs_path.read_text(encoding="utf-8"), Loader=_ConfigLoader) or {}
    except yaml.YAMLError:
        payload = {}
    docs_dir_setting = payload.get("docs_dir")
    if docs_dir_setting is None or docs_dir_setting in {".", ""}:
        return site_root
    docs_dir = Path(str(docs_dir_setting))
    if not docs_dir.is_absolute():
        docs_dir = (site_root / docs_dir).resolve()
    return docs_dir


def _create_default_mkdocs(mkdocs_path: Path, site_root: Path) -> Path:
    """Create a comprehensive MkDocs configuration for blog and return the docs directory path.

    MODERN (Regression Fix): Creates mkdocs.yml in .egregora/ with docs_dir: "." to point to root.
    """
    site_name = site_root.name or DEFAULT_SITE_NAME
    env = Environment(loader=FileSystemLoader(str(SITE_TEMPLATES_DIR)), autoescape=select_autoescape())

    # NEW: Context for root-level content structure
    context = {
        "site_name": site_name,
        "blog_dir": "posts",  # Posts at root level
        "docs_dir": ".",  # Docs dir is site root
    }

    # Resolve paths first to get mkdocs_config_path in .egregora/
    site_paths = resolve_site_paths(site_root)

    # Create mkdocs.yml in .egregora/ directory
    mkdocs_config_path = site_paths.mkdocs_config_path
    mkdocs_template = env.get_template("mkdocs.yml.jinja")
    mkdocs_content = mkdocs_template.render(**context)
    mkdocs_config_path.parent.mkdir(parents=True, exist_ok=True)
    mkdocs_config_path.write_text(mkdocs_content, encoding="utf-8")
    logger.info("Created .egregora/mkdocs.yml")

    # Create site structure
    _create_site_structure(site_paths, env, context)
    return site_paths.docs_dir


def _create_site_structure(site_paths: SitePaths, env: Environment, context: dict[str, Any]) -> None:
    """Create essential directories and index files for the blog structure.

    SIMPLIFIED (Alpha): Always create .egregora/ structure.
    MODERN (Regression Fix): Content at root level (not in docs/).
    """
    # Create .egregora/ structure (new!)
    _create_egregora_structure(site_paths, env)

    # Create content structure at root level (not in docs/)
    site_root = site_paths.site_root
    posts_dir = site_paths.posts_dir
    profiles_dir = site_paths.profiles_dir
    media_dir = site_paths.media_dir

    # Create main content directories at root
    for directory in (posts_dir, profiles_dir, media_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # Create media subdirectories with .gitkeep
    for subdir in ["images", "videos", "audio", "documents"]:
        media_subdir = media_dir / subdir
        media_subdir.mkdir(exist_ok=True)
        (media_subdir / ".gitkeep").touch()

    # Create journal directory for agent logs
    journal_dir = posts_dir / "journal"
    journal_dir.mkdir(exist_ok=True)
    (journal_dir / ".gitkeep").touch()

    # Create root-level README and .gitignore
    readme_path = site_root / "README.md"
    if not readme_path.exists():
        template = env.get_template("README.md.jinja")
        content = template.render(**context)
        readme_path.write_text(content, encoding="utf-8")

    gitignore_path = site_root / ".gitignore"
    if not gitignore_path.exists():
        template = env.get_template(".gitignore.jinja")
        content = template.render(**context)
        gitignore_path.write_text(content, encoding="utf-8")

    # Create index files at root level
    homepage_path = site_root / "index.md"
    if not homepage_path.exists():
        template = env.get_template("docs/index.md.jinja")
        content = template.render(**context)
        homepage_path.write_text(content, encoding="utf-8")

    about_path = site_root / "about.md"
    if not about_path.exists():
        template = env.get_template("docs/about.md.jinja")
        content = template.render(**context)
        about_path.write_text(content, encoding="utf-8")

    profiles_index_path = profiles_dir / "index.md"
    if not profiles_index_path.exists():
        template = env.get_template("docs/profiles/index.md.jinja")
        content = template.render(**context)
        profiles_index_path.write_text(content, encoding="utf-8")

    media_index_path = media_dir / "index.md"
    if not media_index_path.exists():
        template = env.get_template("docs/media/index.md.jinja")
        content = template.render(**context)
        media_index_path.write_text(content, encoding="utf-8")

    _render_egregora_config(site_paths.site_root, env, context)


def _copy_default_prompts(target_prompts_dir: Path) -> None:
    """Copy default prompt templates from package to site.

    This implements the "version pinning" strategy: prompts are copied once during
    init and become site-specific. Users can customize without losing changes,
    and Egregora can update defaults without breaking existing sites.

    Args:
        target_prompts_dir: Destination directory (.egregora/prompts/)

    """
    # Find source prompts directory in package
    package_prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

    if not package_prompts_dir.exists():
        logger.warning("Package prompts directory not found: %s", package_prompts_dir)
        return

    # Copy all .jinja files from package to site
    prompt_files_copied = 0
    for source_file in package_prompts_dir.rglob("*.jinja"):
        # Compute relative path to preserve directory structure
        rel_path = source_file.relative_to(package_prompts_dir)
        target_file = target_prompts_dir / rel_path

        # Only copy if target doesn't exist (don't overwrite customizations)
        if not target_file.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                target_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
                prompt_files_copied += 1
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Failed to copy prompt %s: %s", source_file.name, e)

    if prompt_files_copied > 0:
        logger.info("Copied %d default prompt templates to %s", prompt_files_copied, target_prompts_dir)


def _create_egregora_structure(site_paths: SitePaths, env: Environment | None = None) -> None:
    """Create .egregora/ directory structure with templates.

    Creates:
    - .egregora/config.yml (from template with comments)
    - .egregora/prompts/ (for custom prompt overrides + default copies)
    - .egregora/prompts/system/ (writer, editor prompts)
    - .egregora/prompts/enrichment/ (URL, media prompts)
    - .egregora/prompts/README.md (usage guide)
    - .egregora/.gitignore (ignore ephemeral data)

    Version Pinning: Default prompts are copied (not symlinked) so sites have
    stable prompt versions that can be customized independently.
    """
    egregora_dir = site_paths.egregora_dir
    egregora_dir.mkdir(parents=True, exist_ok=True)

    # Use template environment if not provided
    if env is None:
        env = Environment(loader=FileSystemLoader(str(SITE_TEMPLATES_DIR)), autoescape=select_autoescape())

    # Create config.yml from template (with comments)
    config_path = site_paths.config_path
    if not config_path.exists():
        try:
            config_template = env.get_template(".egregora/config.yml.jinja")
            config_content = config_template.render()
            config_path.write_text(config_content, encoding="utf-8")
            logger.info("Created .egregora/config.yml from template")
        except (OSError, TemplateError) as e:
            # Fallback to Pydantic default if template fails
            logger.warning("Failed to render config template: %s. Using Pydantic default.", e)
            create_default_config(site_paths.site_root)

    # Create prompts directory structure and copy default prompts
    prompts_dir = site_paths.prompts_dir
    prompts_dir.mkdir(exist_ok=True)

    # Create subdirectories for prompt categories
    (prompts_dir / "system").mkdir(exist_ok=True)
    (prompts_dir / "enrichment").mkdir(exist_ok=True)

    # Copy default prompts from package to site (version pinning strategy)
    _copy_default_prompts(prompts_dir)

    # Create prompts README from template
    prompts_readme = prompts_dir / "README.md"
    if not prompts_readme.exists():
        try:
            readme_template = env.get_template(".egregora/prompts/README.md.jinja")
            readme_content = readme_template.render()
            prompts_readme.write_text(readme_content, encoding="utf-8")
            logger.info("Created .egregora/prompts/README.md")
        except (OSError, TemplateError) as e:
            # Fallback to simple README if template fails
            logger.warning("Failed to render prompts README template: %s. Using simple version.", e)
            prompts_readme.write_text(
                "# Custom Prompts\n\n"
                "Place custom prompt overrides here with same structure as package defaults.\n\n"
                "See https://docs.egregora.ai for more information.\n",
                encoding="utf-8",
            )

    # Create .gitignore
    gitignore = egregora_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# Ephemeral data (regenerated on each run)\n"
            ".cache/\n"
            "rag/*.duckdb\n"
            "rag/*.parquet\n"
            "rag/*.duckdb.wal\n"
            "\n"
            "# Python cache\n"
            "__pycache__/\n"
            "*.pyc\n",
            encoding="utf-8",
        )
        logger.info("Created .egregora/.gitignore")


def _render_egregora_config(site_root: Path, env: Environment, context: dict[str, Any]) -> None:
    """Legacy: Render .egregora configuration templates using Jinja2.

    DEPRECATED (Alpha): Use _create_egregora_structure instead.
    Kept temporarily for compatibility during transition.
    """
    # This function is now a no-op - _create_egregora_structure handles it


__all__ = ["ensure_mkdocs_project"]

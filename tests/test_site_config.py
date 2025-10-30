from pathlib import Path

from egregora.site_config import DEFAULT_DOCS_DIR, MkDocsConfig, _resolve_docs_dir


def _config_with_docs_dir(value: str | None) -> MkDocsConfig:
    return MkDocsConfig.from_mapping({"docs_dir": value})


def test_resolve_docs_dir_empty_string_uses_site_root(tmp_path: Path) -> None:
    config = _config_with_docs_dir("")

    resolved = _resolve_docs_dir(tmp_path, config)

    assert resolved == tmp_path


def test_resolve_docs_dir_dot_slash_uses_site_root(tmp_path: Path) -> None:
    config = _config_with_docs_dir("./")

    resolved = _resolve_docs_dir(tmp_path, config)

    assert resolved == tmp_path


def test_resolve_docs_dir_none_defaults_to_docs(tmp_path: Path) -> None:
    config = MkDocsConfig.empty()

    resolved = _resolve_docs_dir(tmp_path, config)

    assert resolved == (tmp_path / DEFAULT_DOCS_DIR).resolve()


def test_resolve_docs_dir_dot_uses_site_root(tmp_path: Path) -> None:
    config = _config_with_docs_dir(".")

    resolved = _resolve_docs_dir(tmp_path, config)

    assert resolved == tmp_path

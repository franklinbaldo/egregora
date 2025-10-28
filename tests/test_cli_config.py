import pytest
import typer

from src.egregora.cli import _resolve_gemini_key, _validate_and_run_process
from src.egregora.config_types import ProcessConfig


def test_resolve_gemini_key_prefers_cli_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

    result = _resolve_gemini_key("flag-key")

    assert result == "flag-key"


def test_resolve_gemini_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

    result = _resolve_gemini_key(None)

    assert result == "env-key"


def test_resolve_gemini_key_returns_none_without_sources(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = _resolve_gemini_key(None)

    assert result is None


def test_validate_process_uses_cli_override(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

    captured = {}

    def fake_process_whatsapp_export(*args, **kwargs):
        captured["api_key"] = kwargs["gemini_api_key"]
        return {}

    monkeypatch.setattr(
        "src.egregora.cli.process_whatsapp_export", fake_process_whatsapp_export
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    monkeypatch.setattr(
        "src.egregora.cli.find_mkdocs_file", lambda _path: site_dir / "mkdocs.yml"
    )

    zip_path = tmp_path / "chat.zip"
    zip_path.write_text("dummy")

    config = ProcessConfig(
        zip_file=zip_path,
        output_dir=site_dir,
        gemini_key="flag-key",
    )

    _validate_and_run_process(config)

    assert captured["api_key"] == "flag-key"


def test_validate_process_uses_env_when_cli_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")

    captured = {}

    def fake_process_whatsapp_export(*args, **kwargs):
        captured["api_key"] = kwargs["gemini_api_key"]
        return {}

    monkeypatch.setattr(
        "src.egregora.cli.process_whatsapp_export", fake_process_whatsapp_export
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    monkeypatch.setattr(
        "src.egregora.cli.find_mkdocs_file", lambda _path: site_dir / "mkdocs.yml"
    )

    zip_path = tmp_path / "chat.zip"
    zip_path.write_text("dummy")

    config = ProcessConfig(
        zip_file=zip_path,
        output_dir=site_dir,
        gemini_key=None,
    )

    _validate_and_run_process(config)

    assert captured["api_key"] == "env-key"


def test_validate_process_exits_without_any_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    def fake_process_whatsapp_export(*args, **kwargs):
        raise AssertionError("Should not be called when API key is missing")

    monkeypatch.setattr(
        "src.egregora.cli.process_whatsapp_export", fake_process_whatsapp_export
    )
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    monkeypatch.setattr(
        "src.egregora.cli.find_mkdocs_file", lambda _path: site_dir / "mkdocs.yml"
    )

    zip_path = tmp_path / "chat.zip"
    zip_path.write_text("dummy")

    config = ProcessConfig(
        zip_file=zip_path,
        output_dir=site_dir,
        gemini_key=None,
    )

    with pytest.raises(typer.Exit):
        _validate_and_run_process(config)

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from typer.testing import CliRunner

CLI_MODULE_NAME = "egregora.cli"
CLI_PATH = Path(__file__).resolve().parents[1] / "src" / "egregora" / "cli.py"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location(CLI_MODULE_NAME, CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[CLI_MODULE_NAME] = module
    assert spec.loader is not None  # for mypy type narrowing
    spec.loader.exec_module(module)
    return module


def test_rank_command_requires_optional_extra(monkeypatch, tmp_path):
    """The rank command should guide users to install the optional extra when missing."""

    sys.modules.pop(CLI_MODULE_NAME, None)

    original_import_module = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name.startswith("egregora.ranking"):
            raise ModuleNotFoundError("egregora.ranking")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    cli_module = _load_cli_module()
    runner = CliRunner()

    result = runner.invoke(cli_module.app, ["rank", str(tmp_path)])

    assert result.exit_code == 1
    assert "egregora[ranking]" in result.stdout
    assert "Missing dependency" in result.stdout

    help_result = runner.invoke(cli_module.app, ["--help"])
    commands_section = help_result.stdout.split("Commands:", 1)[-1]
    assert "rank" not in commands_section

    sys.modules.pop(CLI_MODULE_NAME, None)

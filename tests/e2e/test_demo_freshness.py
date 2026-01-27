import filecmp
import os
from pathlib import Path

import pytest
from egregora.output_sinks.mkdocs.scaffolding import ensure_mkdocs_project

from egregora.config import load_egregora_config
from egregora.constants import SourceType
from egregora.orchestration.context import PipelineRunParams
from egregora.orchestration.pipelines.write import run as run_write_pipeline

# Determine the project root to reliably find the 'demo' directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
DEMO_DIR = PROJECT_ROOT / "demo"
SAMPLE_INPUT_FILE = PROJECT_ROOT / "tests/fixtures/Conversa do WhatsApp com Teste.zip"


def are_dirs_equal(dir1: Path, dir2: Path) -> tuple[bool, str]:
    """
    Compare two directories recursively. Returns (are_equal, report_string).
    Ignores the .gitkeep file which is not part of the generated output.
    """
    ignore_list = [".gitkeep", ".DS_Store", "__pycache__"]
    comparison = filecmp.dircmp(dir1, dir2, ignore=ignore_list)

    if comparison.left_only or comparison.right_only or comparison.diff_files or comparison.funny_files:
        report = []
        if comparison.left_only:
            report.append(f"Only in {dir1}: {comparison.left_only}")
        if comparison.right_only:
            report.append(f"Only in {dir2}: {comparison.right_only}")
        if comparison.diff_files:
            report.append(f"Different files: {comparison.diff_files}")
        if comparison.funny_files:
            report.append(f"Could not compare: {comparison.funny_files}")
        return False, "\n".join(report)

    for subdir in comparison.common_dirs:
        are_equal, report_str = are_dirs_equal(dir1 / subdir, dir2 / subdir)
        if not are_equal:
            return False, f"Difference in subdir '{subdir}':\n{report_str}"

    return True, ""


@pytest.mark.e2e
@pytest.mark.slow
def test_demo_directory_is_up_to_date(tmp_path: Path):
    """
    Tests that the committed `demo/` directory is up-to-date by generating a fresh
    demo site and comparing it against the committed version.

    Note: This test is skipped in CI environments because:
    1. The demo directory is gitignored and not committed
    2. Generating a demo requires real API keys which may not be available in CI
    """
    # Skip in CI environments
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        pytest.skip("Skipping demo freshness test in CI environment")

    if not DEMO_DIR.exists():
        pytest.skip(f"Demo directory not found at {DEMO_DIR} - run 'uv run egregora demo' to generate it")

    if not SAMPLE_INPUT_FILE.exists():
        pytest.skip(f"Sample input file not found at {SAMPLE_INPUT_FILE}")

    temp_demo_path = tmp_path / "fresh_demo"
    temp_demo_path.mkdir()

    # Initialize a new mkdocs project in the temporary directory
    ensure_mkdocs_project(temp_demo_path)

    # We need a minimal config. Since the demo command doesn't rely on a config
    # from the output directory, we load from the project root's default.
    config = load_egregora_config(DEMO_DIR)
    # Disable enrichment to prevent network calls during the test
    config.enrichment.enabled = False

    # Mimic the parameters used by the `egregora demo` command
    run_params = PipelineRunParams(
        output_dir=temp_demo_path,
        config=config,
        source_type=SourceType.WHATSAPP.value,
        input_path=SAMPLE_INPUT_FILE,
        refresh="all",  # `force=True` in the CLI command translates to this
        smoke_test=True,  # Run in offline mode to avoid API errors
    )

    # Run the pipeline to generate the fresh demo
    try:
        run_write_pipeline(run_params)
    except Exception as exc:
        pytest.fail(f"Demo site generation failed with an exception: {exc}")

    # Compare the generated demo with the committed one
    are_equal, report = are_dirs_equal(temp_demo_path, DEMO_DIR)

    assert are_equal, (
        "The committed 'demo/' directory is out of date.\n"
        "Run 'uv run egregora demo' and commit the changes.\n\n"
        f"Differences found:\n{report}"
    )

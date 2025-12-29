from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from egregora.data_primitives.document import SiteScaffolder
from egregora.init.exceptions import ScaffoldingExecutionError, ScaffoldingPathError
from egregora.init.scaffolding import ensure_mkdocs_project


@patch("egregora.init.scaffolding.create_output_sink")
def test_ensure_mkdocs_project_raises_on_path_resolution_failure(mock_create_output_sink, tmp_path: Path):
    """
    GIVEN a non-scaffolding adapter and a failing MkDocsPaths resolution
    WHEN ensure_mkdocs_project is called
    THEN it should raise a specific ScaffoldingPathError instead of swallowing the error.
    """
    site_root = tmp_path
    original_error = OSError("Test OS Error: Permission denied")

    # Configure the mock to return an object that is NOT a SiteScaffolder.
    # This forces the code to enter the `if not isinstance(...)` block.
    mock_create_output_sink.return_value = Mock(spec=[])

    # This mock simulates the failure in the `try...except` block I'm targeting.
    with patch("egregora.init.scaffolding.MkDocsPaths", side_effect=original_error):
        with pytest.raises(ScaffoldingPathError) as exc_info:
            ensure_mkdocs_project(site_root)

        # Check that the custom exception was raised with the correct context.
        assert exc_info.value.site_root == site_root
        assert exc_info.value.__cause__ is original_error


@patch("egregora.init.scaffolding.create_output_sink")
def test_ensure_mkdocs_project_raises_on_scaffolding_failure(mock_create_output_sink, tmp_path: Path):
    """
    GIVEN a scaffolding adapter that fails during scaffold execution
    WHEN ensure_mkdocs_project is called
    THEN it should raise a specific ScaffoldingExecutionError.
    """
    site_root = tmp_path
    original_error = RuntimeError("Test Scaffolding Error")

    # Mock the scaffolder and its scaffold method to raise an error.
    mock_scaffolder = Mock(spec=SiteScaffolder)
    # The spec requires the method to be explicitly part of the mock's interface
    mock_scaffolder.scaffold = Mock(side_effect=original_error)
    mock_create_output_sink.return_value = mock_scaffolder

    with patch("egregora.init.scaffolding.hasattr", return_value=False):
        with pytest.raises(ScaffoldingExecutionError) as exc_info:
            ensure_mkdocs_project(site_root)

    # Check that the custom exception was raised with the correct context.
    assert exc_info.value.site_root == site_root
    assert exc_info.value.__cause__ is original_error

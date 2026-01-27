<<<<<<< HEAD
from datetime import date
from unittest.mock import patch

import pytest

from egregora.orchestration.pipelines.write import (
    _ensure_site_initialized,
    _validate_dates,
    _validate_timezone_arg,
)


=======
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from datetime import date

from egregora.orchestration.pipelines.write import (
    _validate_dates,
    _validate_timezone_arg,
    _ensure_site_initialized,
)

>>>>>>> origin/pr/2730
def test_validate_dates_valid():
    """Verify valid date strings are parsed correctly."""
    f, t = _validate_dates("2023-01-01", "2023-12-31")
    assert f == date(2023, 1, 1)
    assert t == date(2023, 12, 31)

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
def test_validate_dates_none():
    """Verify None values are handled."""
    f, t = _validate_dates(None, None)
    assert f is None
    assert t is None

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
def test_validate_dates_invalid_from():
    """Verify invalid from_date raises SystemExit."""
    with pytest.raises(SystemExit):
        _validate_dates("invalid", None)

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
def test_validate_dates_invalid_to():
    """Verify invalid to_date raises SystemExit."""
    with pytest.raises(SystemExit):
        _validate_dates(None, "invalid")

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
def test_validate_timezone_valid():
    """Verify valid timezone passes."""
    _validate_timezone_arg("UTC")

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
def test_validate_timezone_invalid():
    """Verify invalid timezone raises SystemExit."""
    with pytest.raises(SystemExit):
        _validate_timezone_arg("Invalid/Zone")

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
@patch("egregora.orchestration.pipelines.write.MkDocsSiteScaffolder")
def test_ensure_site_initialized_exists(mock_scaffolder, tmp_path):
    """Verify scaffolding is skipped if config exists."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()
    (output_dir / ".egregora.toml").touch()

    _ensure_site_initialized(output_dir)
    mock_scaffolder.assert_not_called()

<<<<<<< HEAD

=======
>>>>>>> origin/pr/2730
@patch("egregora.orchestration.pipelines.write.MkDocsSiteScaffolder")
def test_ensure_site_initialized_creates(mock_scaffolder, tmp_path):
    """Verify scaffolding is called if config missing."""
    output_dir = tmp_path / "new_site"

    _ensure_site_initialized(output_dir)

    assert output_dir.exists()
    mock_scaffolder.return_value.scaffold_site.assert_called_once_with(output_dir, site_name="new_site")

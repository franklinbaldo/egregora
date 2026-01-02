from pathlib import Path
from unittest.mock import MagicMock

import pytest

from egregora.config.settings import EgregoraConfig
from egregora.orchestration.pipelines.write import _create_database_backend


def test_create_database_backend_raises_value_error_on_empty_uri():
    """Verify that _create_database_backend raises ValueError for an empty database URI."""
    mock_config = MagicMock(spec=EgregoraConfig)
    mock_config.database = MagicMock()
    mock_config.database.pipeline_db = ""

    with pytest.raises(ValueError, match="must be a non-empty connection URI"):
        _create_database_backend(Path("/tmp"), mock_config)

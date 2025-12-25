
import pytest
from unittest.mock import MagicMock
from src.egregora.database.run_store import RunStore

def test_run_store_initialization():
    mock_storage = MagicMock()
    run_store = RunStore(mock_storage)
    assert run_store.storage is mock_storage

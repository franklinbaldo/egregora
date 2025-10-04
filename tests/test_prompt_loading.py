"""Tests for prompt loading functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from egregora.pipeline import _load_prompt


def test_load_prompt_from_local_file():
    """Test loading prompt from local editable file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        prompt_file = temp_path / "test_prompt.md"
        prompt_content = "# Test Prompt\n\nThis is a test prompt."
        prompt_file.write_text(prompt_content, encoding="utf-8")
        
        # Mock the _PROMPTS_DIR to point to our temp directory
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            result = _load_prompt("test_prompt.md")
            assert result == prompt_content.strip()


def test_load_prompt_from_package_resources():
    """Test loading prompt from package resources when local file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Mock _PROMPTS_DIR to point to empty directory
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            # Mock the resources.files to return our test content
            mock_content = "# Package Prompt\n\nThis is from package resources."
            
            with patch("egregora.pipeline.resources.files") as mock_resources:
                mock_files = mock_resources.return_value
                mock_joinpath = mock_files.joinpath.return_value
                mock_joinpath.read_text.return_value = mock_content
                
                result = _load_prompt("test_prompt.md")
                assert result == mock_content.strip()
                
                # Verify the correct package was used
                mock_resources.assert_called_once_with("egregora")
                mock_files.joinpath.assert_called_once_with("prompts/test_prompt.md")


def test_load_prompt_empty_local_file_raises_error():
    """Test that empty local files raise ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        prompt_file = temp_path / "empty_prompt.md"
        prompt_file.write_text("   \n\t  \n   ", encoding="utf-8")  # Only whitespace
        
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            with pytest.raises(ValueError, match="Prompt file .* is empty"):
                _load_prompt("empty_prompt.md")


def test_load_prompt_empty_package_resource_raises_error():
    """Test that empty package resources raise ValueError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            with patch("egregora.pipeline.resources.files") as mock_resources:
                mock_files = mock_resources.return_value
                mock_joinpath = mock_files.joinpath.return_value
                mock_joinpath.read_text.return_value = "   \n\t  \n   "  # Only whitespace
                
                with pytest.raises(ValueError, match="Prompt resource .* is empty"):
                    _load_prompt("empty_prompt.md")


def test_load_prompt_missing_file_raises_error():
    """Test that missing prompt files raise FileNotFoundError."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            with patch("egregora.pipeline.resources.files") as mock_resources:
                mock_files = mock_resources.return_value
                mock_joinpath = mock_files.joinpath.return_value
                mock_joinpath.read_text.side_effect = FileNotFoundError("File not found")
                
                with pytest.raises(FileNotFoundError, match="Prompt file .* is missing"):
                    _load_prompt("nonexistent_prompt.md")


def test_load_prompt_prefers_local_over_package():
    """Test that local files take precedence over package resources."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        prompt_file = temp_path / "priority_test.md"
        local_content = "# Local Prompt\n\nThis is from local file."
        prompt_file.write_text(local_content, encoding="utf-8")
        
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            with patch("egregora.pipeline.resources.files") as mock_resources:
                # This should not be called since local file exists
                mock_files = mock_resources.return_value
                mock_joinpath = mock_files.joinpath.return_value
                mock_joinpath.read_text.return_value = "# Package Prompt\n\nThis should not be used."
                
                result = _load_prompt("priority_test.md")
                assert result == local_content.strip()
                
                # Verify package resources were not accessed
                mock_resources.assert_not_called()


def test_load_prompt_strips_whitespace():
    """Test that loaded prompts have leading/trailing whitespace stripped."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        prompt_file = temp_path / "whitespace_test.md"
        content_with_whitespace = "\n\n  # Test Prompt\n\nContent here.  \n\n\t  \n"
        expected_content = "# Test Prompt\n\nContent here."
        prompt_file.write_text(content_with_whitespace, encoding="utf-8")
        
        with patch("egregora.pipeline._PROMPTS_DIR", temp_path):
            result = _load_prompt("whitespace_test.md")
            assert result == expected_content
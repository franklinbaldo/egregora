"""Unit tests for avatar processing."""

from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from egregora.agents.avatar import (
    AvatarContext,
    _download_avatar_from_command,
    _process_set_avatar_command,
)


class AvatarProcessingTest(unittest.TestCase):
    """Test suite for avatar processing."""

    @patch("egregora.agents.avatar.download_avatar_from_url")
    @patch("egregora.agents.avatar.enrich_avatar")
    def test_download_avatar_from_command(self, mock_enrich_avatar, mock_download_avatar):
        """Verify avatar download and enrichment process."""
        mock_download_avatar.return_value = ("mock_uuid", Path("/fake/avatar.jpg"))
        context = AvatarContext(
            docs_dir=Path("/docs"),
            media_dir=Path("/media"),
            profiles_dir=Path("/profiles"),
            vision_model="mock_model",
        )

        avatar_url = _download_avatar_from_command(
            value="http://example.com/avatar.jpg",
            author_uuid="author1",
            timestamp=datetime.now(),
            context=context,
        )

        self.assertEqual(avatar_url, "http://example.com/avatar.jpg")
        mock_download_avatar.assert_called_once()
        mock_enrich_avatar.assert_called_once()

    @patch("egregora.agents.avatar._download_avatar_from_command")
    @patch("egregora.agents.avatar.update_profile_avatar")
    def test_process_set_avatar_command(self, mock_update_profile, mock_download_avatar):
        """Verify profile update after avatar processing."""
        mock_download_avatar.return_value = "http://example.com/new_avatar.jpg"
        context = AvatarContext(
            docs_dir=Path("/docs"),
            media_dir=Path("/media"),
            profiles_dir=Path("/profiles"),
            vision_model="mock_model",
        )

        result = _process_set_avatar_command(
            author_uuid="author1",
            timestamp=datetime.now(),
            context=context,
            value="http://example.com/new_avatar.jpg",
        )

        self.assertEqual(result, "✅ Avatar set for author1")
        mock_download_avatar.assert_called_once()
        mock_update_profile.assert_called_once()


if __name__ == "__main__":
    unittest.main()

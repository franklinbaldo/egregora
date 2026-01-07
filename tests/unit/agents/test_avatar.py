"""Tests for egregora.agents.avatar."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import call, patch

import pytest
import respx
from httpx import Response

from egregora.agents.avatar import AvatarProcessingError, download_avatar_from_url
from egregora.security.ssrf import SSRFValidationError


@respx.mock
@patch("egregora.agents.avatar.validate_public_url")
def test_download_avatar_blocks_ssrf_via_redirect(mock_validate_public_url, tmp_path: Path):
    """Should validate every URL in a redirect chain and block a private IP."""
    public_url = "https://public.site/avatar.jpg"
    private_url = "http://127.0.0.1/secret.jpg"

    def validation_side_effect(url):
        if "127.0.0.1" in url:
            raise SSRFValidationError("URL resolves to blocked IP address")
        # For the public URL, do nothing (pass validation)

    mock_validate_public_url.side_effect = validation_side_effect

    # Mock the HTTP redirect
    respx.get(public_url).mock(
        return_value=Response(302, headers={"Location": private_url})
    )

    media_dir = tmp_path / "media"
    media_dir.mkdir()

    # The download function should catch the SSRFValidationError and
    # wrap it in its own exception type.
    with pytest.raises(
        AvatarProcessingError, match="URL resolves to blocked IP address"
    ):
        download_avatar_from_url(public_url, media_dir)

    # CRITICAL: Verify that the validator was called for both the initial
    # public URL and the subsequent private URL from the redirect.
    assert mock_validate_public_url.call_count == 2
    mock_validate_public_url.assert_has_calls([call(public_url), call(private_url)])

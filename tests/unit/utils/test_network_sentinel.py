from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest
import respx
from httpx import Response

from egregora.agents.avatar import AvatarProcessingError, download_avatar_from_url


@pytest.mark.asyncio
@respx.mock
async def test_download_avatar_toctou_exploit_via_redirect(tmp_path: Path, monkeypatch):
    """
    GIVEN a URL that passes an initial security scan
    WHEN the same URL is fetched again for download
    AND it returns a redirect to a blocked private IP address
    THEN the download function should raise an AvatarProcessingError
    """
    public_url = "http://public.safe/avatar.jpg"
    private_url = "http://127.0.0.1/internal/data"
    media_dir = tmp_path

    # Mock DNS resolution to prevent `socket.gaierror`.
    def mock_getaddrinfo(host, *args, **kwargs):
        if host == "public.safe":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
        if host == "127.0.0.1":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        msg = f"[Errno -2] Name or service not known: {host}"
        raise socket.gaierror(msg)

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    # Mock the initial HEAD request used by `validate_public_url`.
    respx.head(public_url).mock(return_value=Response(200))

    # Mock the GET request to return a redirect response.
    # Manually construct the `next_request` attribute to fix the test environment.
    redirect_response = Response(302, headers={"Location": private_url})
    redirect_response.next_request = httpx.Request("GET", private_url)
    respx.get(public_url).mock(return_value=redirect_response)

    # Mock the private URL. If the exploit succeeds, this will be accessed.
    respx.get(private_url).mock(return_value=Response(200, content=b"malicious_data"))

    # This test verifies that a malicious redirect during an avatar download is blocked.
    # The `download_avatar_from_url` function should raise an error when the
    # download attempt is redirected to a private IP.
    with pytest.raises(AvatarProcessingError, match="URL resolves to blocked IP address"):
        download_avatar_from_url(url=public_url, media_dir=media_dir)

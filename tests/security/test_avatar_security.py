from pathlib import Path

import pytest
import respx
from httpx import Response

from egregora.agents.avatar import AvatarProcessingError, download_avatar_from_url

# A known public domain that resolves to a public IP
PUBLIC_URL = "http://example.com/avatar.png"
# A URL with a private IP address that should be blocked
PRIVATE_URL = "http://127.0.0.1/internal/avatar.png"


@respx.mock
def test_ssrf_error_message_is_not_masked(tmp_path: Path):
    """
    Verify that a specific SSRF error is raised and not masked by a generic error.
    An attacker could use a redirect from a public URL to a private one. The initial
    check might pass, but the redirect should be caught, and the error should be specific.
    """
    # 1. Mock the initial request to a public URL.
    #    This request will return a redirect (302) to the private URL.
    respx.get(PUBLIC_URL).mock(return_value=Response(302, headers={"Location": PRIVATE_URL}))

    # 2. Mock the subsequent request to the private URL, which would be followed by httpx.
    #    This endpoint doesn't need to return anything, as the validation happens
    #    on the request hook before the request is sent.
    respx.get(PRIVATE_URL).mock(return_value=Response(200, content=b"fake-image-data"))

    # 3. Call the download function, which is expected to fail.
    with pytest.raises(AvatarProcessingError) as exc_info:
        download_avatar_from_url(url=PUBLIC_URL, media_dir=tmp_path)

    # 4. Assert that the error message is the specific SSRF validation error,
    #    not the generic "Failed to download avatar" message.
    error_message = str(exc_info.value)
    assert "resolves to blocked IP" in error_message
    assert "Access to private/internal networks is not allowed" in error_message
    assert "Failed to download avatar" not in error_message

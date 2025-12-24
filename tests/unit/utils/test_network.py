from __future__ import annotations

import socket
from http.client import SEE_OTHER

import pytest
import respx
from httpx import Response

from egregora.utils.network import SSRFValidationError, validate_public_url


def _fake_addrinfo(*ip_addresses: str) -> list[tuple]:
    return [
        (
            socket.AF_INET6 if ":" in ip else socket.AF_INET,
            socket.SOCK_STREAM,
            0,
            "",
            (ip, 0, 0, 0) if ":" in ip else (ip, 0),
        )
        for ip in ip_addresses
    ]


@respx.mock
def test_validate_public_url_allows_public_ipv4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _fake_addrinfo("93.184.216.34"))
    url = "https://example.com/avatar.png"
    respx.head(url).mock(return_value=Response(200))
    validate_public_url(url)


@pytest.mark.parametrize("url", ["ftp://example.com/file", "mailto:user@example.com"])
def test_validate_public_url_rejects_bad_scheme(url: str) -> None:
    with pytest.raises(SSRFValidationError):
        validate_public_url(url)


def test_validate_public_url_blocks_private_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _fake_addrinfo("192.168.1.10"))

    with pytest.raises(SSRFValidationError) as exc:
        validate_public_url("https://internal.local/avatar.png")

    assert "blocked IP address" in str(exc.value)


def test_validate_public_url_blocks_ipv4_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _fake_addrinfo("::ffff:10.0.0.5"))

    with pytest.raises(SSRFValidationError) as exc:
        validate_public_url("https://example.com/avatar.png")

    assert "blocked IP address" in str(exc.value)


def test_validate_public_url_resolve_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args, **_kwargs):
        msg = "unresolvable"
        raise socket.gaierror(msg)

    monkeypatch.setattr(socket, "getaddrinfo", _raise)

    with pytest.raises(SSRFValidationError):
        validate_public_url("https://does-not-resolve.test")


@respx.mock
def test_validate_public_url_blocks_redirect_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a redirect to a private IP is blocked."""
    public_url = "https://safe.com/redirect"
    private_hostname = "internal.local"
    private_url = f"http://{private_hostname}/secret"

    # Mock DNS resolution for both hostnames
    def mock_getaddrinfo(host, *args, **kwargs):
        if host == "safe.com":
            return _fake_addrinfo("93.184.216.34")  # Public IP
        if host == private_hostname:
            return _fake_addrinfo("192.168.1.1")  # Private IP
        raise socket.gaierror(f"getaddrinfo failed for {host}")

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    # We mock a web server that redirects from the safe URL to the private one.
    respx.head(public_url).mock(return_value=Response(SEE_OTHER, headers={"Location": private_url}))
    # The final destination should not be called, but we mock it just in case.
    respx.head(private_url).mock(return_value=Response(200))

    # The function should validate the initial URL, then follow the redirect,
    # resolve the new hostname, and then fail on the private IP.
    with pytest.raises(SSRFValidationError, match="URL resolves to blocked IP address"):
        validate_public_url(public_url)

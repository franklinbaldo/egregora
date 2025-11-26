from __future__ import annotations

import socket

import pytest

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


def test_validate_public_url_allows_public_ipv4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _fake_addrinfo("93.184.216.34"))

    validate_public_url("https://example.com/avatar.png")


@pytest.mark.parametrize("url", ["ftp://example.com/file", "mailto:user@example.com"])
def test_validate_public_url_rejects_bad_scheme(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: _fake_addrinfo("93.184.216.34"))

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
        raise socket.gaierror("unresolvable")

    monkeypatch.setattr(socket, "getaddrinfo", _raise)

    with pytest.raises(SSRFValidationError):
        validate_public_url("https://does-not-resolve.test")

"""Tests for egregora.security.ssrf."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from egregora.security.ssrf import SSRFValidationError, validate_public_url


class TestValidatePublicUrl:
    """Tests for the validate_public_url function."""

    @patch("socket.getaddrinfo")
    def test_allows_public_ipv4_url(self, mock_getaddrinfo):
        """Should allow a URL that resolves to a public IPv4 address."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        validate_public_url("https://example.com")

    @patch("socket.getaddrinfo")
    def test_allows_public_ipv6_url(self, mock_getaddrinfo):
        """Should allow a URL that resolves to a public IPv6 address."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 443))
        ]
        validate_public_url("https://example.com")

    @patch("socket.getaddrinfo")
    def test_blocks_private_ipv4_url(self, mock_getaddrinfo):
        """Should block a URL that resolves to a private IPv4 address."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 443))]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("https://private.local")

    @patch("socket.getaddrinfo")
    def test_blocks_private_ipv6_url(self, mock_getaddrinfo):
        """Should block a URL that resolves to a private IPv6 address."""
        mock_getaddrinfo.return_value = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", 443))]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("https://private.local")

    @patch("socket.getaddrinfo")
    def test_blocks_ipv4_mapped_ipv6_loopback(self, mock_getaddrinfo):
        """Should block a URL resolving to an IPv4-mapped IPv6 loopback address."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 443))
        ]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("https://localhost.mapped")

    def test_invalid_scheme(self):
        """Should block a URL with a disallowed scheme."""
        with pytest.raises(SSRFValidationError, match="Invalid URL scheme"):
            validate_public_url("ftp://example.com")

    def test_url_without_hostname(self):
        """Should block a URL without a hostname."""
        with pytest.raises(SSRFValidationError, match="URL must have a hostname"):
            validate_public_url("https://")

    @patch("socket.getaddrinfo", side_effect=socket.gaierror("Resolution failed"))
    def test_unresolvable_hostname(self, mock_getaddrinfo):
        """Should block a URL with a hostname that cannot be resolved."""
        with pytest.raises(SSRFValidationError, match="Could not resolve hostname"):
            validate_public_url("https://unresolvable.domain.xyz")

    @patch("socket.getaddrinfo")
    def test_getaddrinfo_returns_empty_list(self, mock_getaddrinfo):
        """Should raise an error if getaddrinfo returns no addresses."""
        mock_getaddrinfo.return_value = []
        with pytest.raises(SSRFValidationError, match="no addresses returned"):
            validate_public_url("https://no.addr.returned")

    @patch("socket.getaddrinfo")
    def test_getaddrinfo_returns_invalid_ip(self, mock_getaddrinfo):
        """Should raise an error if getaddrinfo returns an invalid IP."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", 443))]
        with pytest.raises(SSRFValidationError, match="Invalid IP address"):
            validate_public_url("https://invalid.ip")

    @patch("socket.getaddrinfo")
    def test_dns_rebinding_attack(self, mock_getaddrinfo):
        """Should block a URL that resolves to both a public and private IP."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 443)),
        ]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("https://dns.rebinding.attack")

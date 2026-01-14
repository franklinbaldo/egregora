"""Unit tests for SSRF validation utilities."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from egregora.security.ssrf import SSRFValidationError, validate_public_url


class TestValidatePublicURL:
    """Tests for the validate_public_url function."""

    @patch("socket.getaddrinfo")
    def test_allows_public_ipv4_url(self, mock_getaddrinfo):
        """Should pass validation for a URL resolving to a public IPv4 address."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]
        validate_public_url("http://example.com")
        mock_getaddrinfo.assert_called_with("example.com", None)

    @patch("socket.getaddrinfo")
    def test_blocks_private_ipv4_url(self, mock_getaddrinfo):
        """Should raise SSRFValidationError for a URL resolving to a private IPv4 address."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("http://localhost")

    @patch("socket.getaddrinfo")
    def test_allows_public_ipv6_url(self, mock_getaddrinfo):
        """Should pass validation for a URL resolving to a public IPv6 address."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("2001:4860:4860::8888", 0))]
        validate_public_url("http://example-ipv6.com")

    @patch("socket.getaddrinfo")
    def test_blocks_private_ipv6_url(self, mock_getaddrinfo):
        """Should raise SSRFValidationError for a URL resolving to a private IPv6 (loopback) address."""
        mock_getaddrinfo.return_value = [(None, None, None, None, ("::1", 0))]
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("http://localhost-ipv6")

    def test_rejects_invalid_url_scheme(self):
        """Should raise SSRFValidationError for URLs with disallowed schemes."""
        with pytest.raises(SSRFValidationError, match="Invalid URL scheme"):
            validate_public_url("ftp://example.com")

    def test_rejects_url_without_hostname(self):
        """Should raise SSRFValidationError for URLs without a hostname."""
        with pytest.raises(SSRFValidationError, match="URL must have a hostname"):
            validate_public_url("http:///path/only")

    @patch("socket.getaddrinfo", side_effect=socket.gaierror("Resolution failed"))
    def test_handles_hostname_resolution_failure(self, mock_getaddrinfo):
        """Should raise SSRFValidationError if hostname resolution fails."""
        with pytest.raises(SSRFValidationError, match="Could not resolve hostname"):
            validate_public_url("http://nonexistent.domain.xyz")

    @patch("socket.getaddrinfo")
    def test_blocks_ipv4_mapped_ipv6_address(self, mock_getaddrinfo):
        """Should correctly block an IPv4-mapped IPv6 address in a private range."""
        # ::ffff:192.168.1.1 is the IPv4-mapped version of 192.168.1.1
        mock_getaddrinfo.return_value = [(None, None, None, None, ("::ffff:192.168.1.1", 0))]

        with pytest.raises(SSRFValidationError, match="resolves to blocked IP address"):
            validate_public_url("http://private-mapped-ipv6.com")

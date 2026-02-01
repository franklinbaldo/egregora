"""Behavioral tests for DNS security and pinning."""

import socket
import threading
import ipaddress
from unittest.mock import Mock, patch

import pytest
from egregora.security.dns import (
    safe_dns_validation,
    _pinned_getaddrinfo,
    _get_pinned_hosts,
    _get_blocked_ranges,
    _ensure_patched,
)
from egregora.security.ssrf import SSRFValidationError


# Helper to construct getaddrinfo results
def make_addrinfo(ip: str, port: int = 80, family: int = socket.AF_INET):
    sockaddr = (ip, port)
    if family == socket.AF_INET6:
        sockaddr = (ip, port, 0, 0)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


class TestDNSBehavior:
    """Test DNS pinning and SSRF protection behaviors."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset thread-local state before and after each test."""
        # Clear pins
        if hasattr(threading.local(), "pinned_hosts"):
            del threading.local().pinned_hosts
        if hasattr(threading.local(), "blocked_ranges"):
            del threading.local().blocked_ranges
        yield
        # Cleanup
        if hasattr(threading.local(), "pinned_hosts"):
            del threading.local().pinned_hosts
        if hasattr(threading.local(), "blocked_ranges"):
            del threading.local().blocked_ranges

    @patch("egregora.security.dns._original_getaddrinfo")
    def test_safe_dns_validation_success(self, mock_getaddrinfo):
        """Test successful validation and pinning of a safe public URL."""
        # Arrange
        hostname = "example.com"
        ip = "93.184.216.34"  # Public IP
        mock_getaddrinfo.return_value = [make_addrinfo(ip)]

        # Act
        with safe_dns_validation(f"https://{hostname}"):
            # Assert - Check that the host is pinned in thread-local storage
            pinned = _get_pinned_hosts()
            assert hostname in pinned
            assert ipaddress.IPv4Address(ip) in pinned[hostname]

            # Verify that subsequent getaddrinfo calls use the pinned IP
            # (Note: We're calling _pinned_getaddrinfo directly or via socket if patched)
            results = _pinned_getaddrinfo(hostname, 80)
            assert len(results) == 1
            assert results[0][4][0] == ip  # IP address in sockaddr

        # Assert cleanup
        pinned = _get_pinned_hosts()
        assert hostname not in pinned

    @patch("egregora.security.dns._original_getaddrinfo")
    def test_safe_dns_validation_blocks_private_ip(self, mock_getaddrinfo):
        """Test that validation fails for private IPs (SSRF protection)."""
        # Arrange
        hostname = "internal.local"
        ip = "127.0.0.1"  # Loopback/Private
        mock_getaddrinfo.return_value = [make_addrinfo(ip)]

        # Act & Assert
        with pytest.raises(SSRFValidationError, match="blocked IP address"):
            with safe_dns_validation(f"http://{hostname}"):
                pass

    @patch("egregora.security.dns._original_getaddrinfo")
    def test_pinned_getaddrinfo_uses_pin(self, mock_getaddrinfo):
        """Test that _pinned_getaddrinfo returns pinned IP without calling original."""
        # Arrange
        hostname = "pinned.com"
        pinned_ip = "1.2.3.4"

        # Manually set pin
        _get_pinned_hosts()[hostname] = {ipaddress.IPv4Address(pinned_ip)}

        # Act
        results = _pinned_getaddrinfo(hostname, 80)

        # Assert
        assert len(results) == 1
        assert results[0][4][0] == pinned_ip
        mock_getaddrinfo.assert_not_called()

    @patch("egregora.security.dns._original_getaddrinfo")
    def test_pinned_getaddrinfo_fallback(self, mock_getaddrinfo):
        """Test that _pinned_getaddrinfo falls back to original for unpinned hosts."""
        # Arrange
        hostname = "unpinned.com"
        ip = "5.6.7.8"
        mock_getaddrinfo.return_value = [make_addrinfo(ip)]

        # Act
        results = _pinned_getaddrinfo(hostname, 80)

        # Assert
        assert len(results) == 1
        assert results[0][4][0] == ip
        mock_getaddrinfo.assert_called_once()

    @patch("egregora.security.dns._original_getaddrinfo")
    def test_dns_rebinding_protection(self, mock_getaddrinfo):
        """Test protection against DNS rebinding (blocked IP during context)."""
        # Arrange
        safe_host = "safe.com"
        safe_ip = "8.8.8.8"

        unsafe_host = "attack.com"
        unsafe_ip = "192.168.1.1"  # Private IP

        # Mock returns safe IP first (for context entry), then unsafe IP (for inner call)
        def side_effect(host, *args, **kwargs):
            if host == safe_host:
                return [make_addrinfo(safe_ip)]
            if host == unsafe_host:
                return [make_addrinfo(unsafe_ip)]
            return []

        mock_getaddrinfo.side_effect = side_effect

        # Act & Assert
        with safe_dns_validation(f"https://{safe_host}"):
            # Inside context, try to resolve unsafe host
            # This simulates a redirect to a private IP or a DNS rebind
            with pytest.raises(SSRFValidationError, match="blocked IP address"):
                _pinned_getaddrinfo(unsafe_host, 80)

    def test_safe_dns_validation_invalid_url(self):
        """Test validation of invalid URLs."""
        with pytest.raises(SSRFValidationError, match="Invalid URL scheme"):
            with safe_dns_validation("ftp://example.com"):
                pass

        with pytest.raises(SSRFValidationError, match="URL must have a hostname"):
            with safe_dns_validation("https://"):
                pass

    def test_socket_patching(self):
        """Test that _ensure_patched actually patches socket.getaddrinfo."""
        original = socket.getaddrinfo
        try:
            _ensure_patched()
            assert socket.getaddrinfo == _pinned_getaddrinfo
        finally:
            # Restore just in case, though module might keep it
            socket.getaddrinfo = original

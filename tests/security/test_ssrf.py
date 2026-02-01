"""Tests for SSRF (Server-Side Request Forgery) prevention."""

import ipaddress
import socket

import pytest

from egregora.security.ssrf import (
    DEFAULT_BLOCKED_IP_RANGES,
    SSRFValidationError,
    check_ip_is_public,
    resolve_host_ips,
    validate_public_url,
)


def _fake_addrinfo(*ip_addresses: str) -> list[tuple]:
    """Helper to create fake address info for mocking DNS resolution."""
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


class TestCheckIpIsPublic:
    """Tests for check_ip_is_public function."""

    def test_public_ipv4_passes(self):
        """Public IPv4 addresses should pass validation."""
        public_ip = ipaddress.IPv4Address("8.8.8.8")
        # Should not raise
        check_ip_is_public(public_ip, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)

    def test_private_ipv4_blocked(self):
        """Private IPv4 addresses should be blocked."""
        private_ip = ipaddress.IPv4Address("192.168.1.1")
        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(private_ip, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)
        assert "blocked IP address" in str(exc_info.value)
        assert "192.168.1.1" in str(exc_info.value)

    def test_loopback_ipv4_blocked(self):
        """Loopback IPv4 addresses should be blocked."""
        loopback_ip = ipaddress.IPv4Address("127.0.0.1")
        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(loopback_ip, "http://localhost", DEFAULT_BLOCKED_IP_RANGES)
        assert "blocked IP address" in str(exc_info.value)

    def test_public_ipv6_passes(self):
        """Public IPv6 addresses should pass validation."""
        public_ip = ipaddress.IPv6Address("2001:4860:4860::8888")  # Google DNS
        # Should not raise
        check_ip_is_public(public_ip, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)

    def test_loopback_ipv6_blocked(self):
        """Loopback IPv6 addresses should be blocked."""
        loopback_ip = ipaddress.IPv6Address("::1")
        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(loopback_ip, "http://localhost", DEFAULT_BLOCKED_IP_RANGES)
        assert "blocked IP address" in str(exc_info.value)

    def test_link_local_ipv6_blocked(self):
        """Link-local IPv6 addresses should be blocked."""
        link_local_ip = ipaddress.IPv6Address("fe80::1")
        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(link_local_ip, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)
        assert "blocked IP address" in str(exc_info.value)

    def test_ipv4_mapped_ipv6_with_private_ip_blocked(self):
        """IPv4-mapped IPv6 addresses with private IPs should be blocked.

        This tests the bug fix for proper type narrowing when checking ipv4_mapped.
        IPv4-mapped IPv6 addresses like ::ffff:192.168.1.1 should be detected
        and validated as their underlying IPv4 address.
        """
        # ::ffff:192.168.1.1 (IPv4-mapped IPv6 for 192.168.1.1)
        ipv4_mapped = ipaddress.IPv6Address("::ffff:192.168.1.1")
        assert ipv4_mapped.ipv4_mapped is not None  # Verify it's actually IPv4-mapped

        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(ipv4_mapped, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)
        # Error should mention the IPv4 address in the blocked range
        assert "192.168.1.1" in str(exc_info.value)

    def test_ipv4_mapped_ipv6_with_public_ip_passes(self):
        """IPv4-mapped IPv6 addresses with public IPs should pass validation."""
        # ::ffff:8.8.8.8 (IPv4-mapped IPv6 for Google DNS)
        ipv4_mapped = ipaddress.IPv6Address("::ffff:8.8.8.8")
        assert ipv4_mapped.ipv4_mapped is not None

        # Should not raise
        check_ip_is_public(ipv4_mapped, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)

    def test_ipv4_mapped_ipv6_with_loopback_blocked(self):
        """IPv4-mapped IPv6 addresses with loopback should be blocked."""
        # ::ffff:127.0.0.1 (IPv4-mapped IPv6 for localhost)
        ipv4_mapped = ipaddress.IPv6Address("::ffff:127.0.0.1")
        assert ipv4_mapped.ipv4_mapped is not None

        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(ipv4_mapped, "http://localhost", DEFAULT_BLOCKED_IP_RANGES)
        assert "127.0.0.1" in str(exc_info.value)

    def test_custom_blocked_ranges(self):
        """Custom blocked ranges should be respected."""
        custom_ranges = (ipaddress.ip_network("203.0.113.0/24"),)  # TEST-NET-3
        test_ip = ipaddress.IPv4Address("203.0.113.5")

        with pytest.raises(SSRFValidationError):
            check_ip_is_public(test_ip, "http://example.com", custom_ranges)

    def test_carrier_grade_nat_blocked(self):
        """Carrier-grade NAT addresses should be blocked."""
        cgnat_ip = ipaddress.IPv4Address("100.64.0.1")
        with pytest.raises(SSRFValidationError) as exc_info:
            check_ip_is_public(cgnat_ip, "http://example.com", DEFAULT_BLOCKED_IP_RANGES)
        assert "blocked IP address" in str(exc_info.value)


class TestResolveHostIps:
    """Tests for resolve_host_ips function."""

    def test_resolve_valid_hostname(self, monkeypatch: pytest.MonkeyPatch):
        """Valid hostnames should resolve to IP addresses."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("93.184.216.34")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        ips = resolve_host_ips("example.com")
        assert len(ips) == 1
        assert ipaddress.IPv4Address("93.184.216.34") in ips

    def test_resolve_multiple_ips(self, monkeypatch: pytest.MonkeyPatch):
        """Hostnames resolving to multiple IPs should return all addresses."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("93.184.216.34", "2001:4860:4860::8888")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        ips = resolve_host_ips("example.com")
        assert len(ips) == 2
        assert ipaddress.IPv4Address("93.184.216.34") in ips
        assert ipaddress.IPv6Address("2001:4860:4860::8888") in ips

    def test_resolve_nonexistent_hostname(self, monkeypatch: pytest.MonkeyPatch):
        """Non-existent hostnames should raise SSRFValidationError."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            msg = "Name or service not known"
            raise socket.gaierror(msg)

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_host_ips("nonexistent.example.invalid")
        assert "Could not resolve hostname" in str(exc_info.value)

    def test_resolve_empty_result(self, monkeypatch: pytest.MonkeyPatch):
        """Empty DNS results should raise SSRFValidationError."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return []

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError) as exc_info:
            resolve_host_ips("example.com")
        assert "no addresses returned" in str(exc_info.value)


class TestValidatePublicUrl:
    """Tests for validate_public_url function."""

    def test_valid_public_url(self, monkeypatch: pytest.MonkeyPatch):
        """Valid public URLs should pass validation."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("8.8.8.8")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        # Should not raise
        validate_public_url("http://example.com/path")

    def test_url_with_private_ip_blocked(self, monkeypatch: pytest.MonkeyPatch):
        """URLs resolving to private IPs should be blocked."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("192.168.1.1")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError) as exc_info:
            validate_public_url("http://internal.example.com")
        assert "blocked IP address" in str(exc_info.value)

    def test_invalid_url_scheme(self, monkeypatch: pytest.MonkeyPatch):
        """URLs with invalid schemes should be rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_public_url("ftp://example.com")
        assert "Invalid URL scheme" in str(exc_info.value)

    def test_custom_allowed_schemes(self, monkeypatch: pytest.MonkeyPatch):
        """Custom allowed schemes should be respected."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("8.8.8.8")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        # Should not raise with custom scheme
        validate_public_url("ftp://example.com", allowed_schemes=("ftp",))

    def test_url_without_hostname(self):
        """URLs without hostnames should be rejected."""
        with pytest.raises(SSRFValidationError) as exc_info:
            validate_public_url("http://")
        assert "must have a hostname" in str(exc_info.value)

    def test_localhost_blocked(self, monkeypatch: pytest.MonkeyPatch):
        """Localhost URLs should be blocked."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            if host == "localhost":
                return _fake_addrinfo("127.0.0.1")
            return _fake_addrinfo("8.8.8.8")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError):
            validate_public_url("http://localhost/admin")

    def test_dns_rebinding_attack(self, monkeypatch: pytest.MonkeyPatch):
        """URLs resolving to multiple IPs (including private) should be blocked.

        This protects against DNS rebinding attacks where a hostname resolves
        to both public and private IPs.
        """

        def mock_getaddrinfo(host, *_args, **_kwargs):
            # Malicious DNS returns both public and private IPs
            return _fake_addrinfo("8.8.8.8", "192.168.1.1")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError) as exc_info:
            validate_public_url("http://malicious.example.com")
        assert "blocked IP address" in str(exc_info.value)
        assert "192.168.1.1" in str(exc_info.value)

    def test_ipv6_localhost_blocked(self, monkeypatch: pytest.MonkeyPatch):
        """IPv6 localhost should be blocked."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("::1")

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError):
            validate_public_url("http://localhost6/admin")

    def test_multicast_addresses_blocked(self, monkeypatch: pytest.MonkeyPatch):
        """Multicast addresses should be blocked."""

        def mock_getaddrinfo(host, *_args, **_kwargs):
            return _fake_addrinfo("224.0.0.1")  # Multicast

        monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

        with pytest.raises(SSRFValidationError):
            validate_public_url("http://multicast.example.com")

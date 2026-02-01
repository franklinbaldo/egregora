"""Network utilities, primarily for security functions like SSRF prevention."""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_BLOCKED_IP_RANGES = (
    ipaddress.ip_network("0.0.0.0/8"),  # Current network (often resolves to localhost)
    ipaddress.ip_network("10.0.0.0/8"),  # Private network
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("172.16.0.0/12"),  # Private network
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),  # Private network
    ipaddress.ip_network("198.18.0.0/15"),  # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("fc00::/7"),  # Unique local
)


IPV6_VERSION = 6


class SSRFValidationError(ValueError):
    """Raised when a URL fails SSRF safety validation."""


def check_ip_is_public(
    ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    url: str,
    blocked_ranges: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> None:
    """Verify that an IP address is public and not in any blocked range.

    Recursive for IPv4-mapped IPv6 addresses.

    Args:
        ip_addr: The IP address to check.
        url: The original URL (for logging).
        blocked_ranges: Tuple of blocked networks.

    Raises:
        SSRFValidationError: If IP is in a blocked range.

    """
    # Check for IPv4-mapped IPv6 addresses (e.g., ::ffff:192.0.2.1)
    if isinstance(ip_addr, ipaddress.IPv6Address) and ip_addr.ipv4_mapped:
        ipv4_addr = ip_addr.ipv4_mapped
        logger.debug("Detected IPv4-mapped IPv6 address: %s maps to %s", ip_addr, ipv4_addr)
        check_ip_is_public(ipv4_addr, url, blocked_ranges)

    for blocked_range in blocked_ranges:
        if ip_addr in blocked_range:
            logger.warning(
                "SSRF attempt blocked: %s resolves to %s in blocked range %s", url, ip_addr, blocked_range
            )
            msg = (
                f"URL resolves to blocked IP address: {ip_addr} (in range {blocked_range}). "
                "Access to private/internal networks is not allowed."
            )
            raise SSRFValidationError(msg)


def resolve_host_ips(hostname: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to all its A and AAAA records.

    Args:
        hostname: The hostname to resolve.

    Returns:
        Set of resolved IP addresses.

    Raises:
        SSRFValidationError: If resolution fails or returns no addresses.

    """
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        msg = f"Could not resolve hostname '{hostname}': {exc}"
        raise SSRFValidationError(msg) from exc

    if not addr_info:
        msg = f"Could not resolve hostname '{hostname}': no addresses returned"
        raise SSRFValidationError(msg)

    resolved_ips: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in addr_info:
        ip_str = info[4][0]
        try:
            resolved_ips.add(ipaddress.ip_address(ip_str))
        except ValueError as exc:
            msg = f"Invalid IP address '{ip_str}': {exc}"
            raise SSRFValidationError(msg) from exc

    return resolved_ips


def validate_public_url(
    url: str,
    *,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    blocked_ranges: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = DEFAULT_BLOCKED_IP_RANGES,
) -> None:
    """Validate a URL to guard against SSRF attempts.

    This function resolves the URL's hostname and checks all resulting IP
    addresses against a blocklist of private/reserved networks.
    It does NOT follow redirects; the caller is responsible for validating
    any destination URLs.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - urlparse rarely raises
        msg = f"Invalid URL: {exc}"
        raise SSRFValidationError(msg) from exc

    if parsed.scheme not in allowed_schemes:
        msg = f"Invalid URL scheme: {parsed.scheme}. Only {', '.join(allowed_schemes)} are allowed."
        raise SSRFValidationError(msg)

    if not parsed.hostname:
        msg = "URL must have a hostname"
        raise SSRFValidationError(msg)

    for ip_addr in resolve_host_ips(parsed.hostname):
        check_ip_is_public(ip_addr, url, blocked_ranges)

    logger.info("URL validation passed for: %s", url)

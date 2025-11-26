from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_BLOCKED_IP_RANGES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
)


class SSRFValidationError(ValueError):
    """Raised when a URL fails SSRF safety validation."""


def _validate_ip_is_public(
    ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    url: str,
    blocked_ranges: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> None:
    if ip_addr.version == 6 and ip_addr.ipv4_mapped:
        ipv4_addr = ip_addr.ipv4_mapped
        logger.debug("Detected IPv4-mapped IPv6 address: %s maps to %s", ip_addr, ipv4_addr)
        _validate_ip_is_public(ipv4_addr, url, blocked_ranges)

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


def _resolve_host_ips(hostname: str) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFValidationError(f"Could not resolve hostname '{hostname}': {exc}") from exc

    if not addr_info:
        raise SSRFValidationError(f"Could not resolve hostname '{hostname}': no addresses returned")

    resolved_ips: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in addr_info:
        ip_str = info[4][0]
        try:
            resolved_ips.add(ipaddress.ip_address(ip_str))
        except ValueError as exc:
            raise SSRFValidationError(f"Invalid IP address '{ip_str}': {exc}") from exc

    return resolved_ips


def validate_public_url(
    url: str,
    *,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    blocked_ranges: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = DEFAULT_BLOCKED_IP_RANGES,
) -> None:
    """Validate a URL to guard against SSRF attempts."""

    try:
        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - urlparse rarely raises
        raise SSRFValidationError(f"Invalid URL: {exc}") from exc

    if parsed.scheme not in allowed_schemes:
        raise SSRFValidationError(
            f"Invalid URL scheme: {parsed.scheme}. Only {', '.join(allowed_schemes)} are allowed."
        )

    if not parsed.hostname:
        raise SSRFValidationError("URL must have a hostname")

    for ip_addr in _resolve_host_ips(parsed.hostname):
        _validate_ip_is_public(ip_addr, url, blocked_ranges)

    logger.info("URL validation passed for: %s", url)

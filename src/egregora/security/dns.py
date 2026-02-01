"""DNS security utilities to prevent rebinding attacks."""

from __future__ import annotations

import contextlib
import ipaddress
import logging
import socket
import threading
from collections.abc import Iterator
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from egregora.security.ssrf import (
    DEFAULT_BLOCKED_IP_RANGES,
    SSRFValidationError,
    check_ip_is_public,
    resolve_host_ips,
)

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

logger = logging.getLogger(__name__)

# Thread-local storage for pinned DNS entries
_thread_local = threading.local()


def _get_pinned_hosts() -> dict[str, AbstractSet[ipaddress.IPv4Address | ipaddress.IPv6Address]]:
    """Get the thread-local pinned hosts map."""
    if not hasattr(_thread_local, "pinned_hosts"):
        _thread_local.pinned_hosts = {}
    return _thread_local.pinned_hosts


# Save original getaddrinfo before any patching
_original_getaddrinfo = socket.getaddrinfo


def _pinned_getaddrinfo(
    host: str | bytes | None,
    port: str | int | None,
    family: int = 0,
    type: int = 0,  # noqa: A002 - matching socket.getaddrinfo signature
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[int, int, int, str, tuple]]:
    """Replacement getaddrinfo that checks thread-local pins."""
    # socket.getaddrinfo host can be None or bytes, handle gracefully
    hostname: str | None = None
    if isinstance(host, str):
        hostname = host
    elif isinstance(host, bytes):
        try:
            hostname = host.decode("utf-8")
        except UnicodeDecodeError:
            pass

    if hostname:
        pinned_hosts = _get_pinned_hosts()
        if hostname in pinned_hosts:
            ips = pinned_hosts[hostname]
            results = []
            for ip in ips:
                # Filter by family
                res_family = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
                if family != 0 and family != res_family:
                    continue

                ip_str = str(ip)
                sockaddr: tuple
                if res_family == socket.AF_INET:
                    sockaddr = (ip_str, port)
                else:
                    # IPv6 sockaddr: (address, port, flow info, scope id)
                    sockaddr = (ip_str, port, 0, 0)

                # Defaults if not specified
                res_type = type if type != 0 else socket.SOCK_STREAM
                res_proto = proto if proto != 0 else socket.IPPROTO_TCP

                results.append((res_family, res_type, res_proto, "", sockaddr))

            # If we pinned the host but no IPs matched the requested family, return empty list
            # to prevent falling back to DNS (which might return unsafe IPs)
            return results

    return _original_getaddrinfo(host, port, family, type, proto, flags)


# Global patch state
_patched = False
_patch_lock = threading.Lock()


def _ensure_patched() -> None:
    """Ensure socket.getaddrinfo is patched globally."""
    global _patched
    with _patch_lock:
        if not _patched:
            socket.getaddrinfo = _pinned_getaddrinfo
            _patched = True
            logger.debug("socket.getaddrinfo patched for DNS pinning")


@contextlib.contextmanager
def safe_dns_validation(
    url: str,
    *,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    blocked_ranges: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = DEFAULT_BLOCKED_IP_RANGES,
) -> Iterator[None]:
    """Context manager that prevents DNS Rebinding by pinning resolved IPs.

    Resolves the URL's hostname once, validates the IPs, and then forces
    subsequent socket connections in this thread to use those specific IPs.

    Args:
        url: The URL to validate and pin
        allowed_schemes: Allowed URL schemes
        blocked_ranges: IP ranges to block (e.g. private networks)

    Usage:
        with safe_dns_validation(url):
            response = httpx.get(url)

    """
    _ensure_patched()

    try:
        parsed = urlparse(url)
    except Exception as exc:
        msg = f"Invalid URL: {exc}"
        raise SSRFValidationError(msg) from exc

    if parsed.scheme not in allowed_schemes:
        msg = f"Invalid URL scheme: {parsed.scheme}"
        raise SSRFValidationError(msg)

    hostname = parsed.hostname
    if not hostname:
        msg = "URL must have a hostname"
        raise SSRFValidationError(msg)

    # 1. Resolve and Validate
    # Use internal helper to resolve IPs once
    resolved_ips = resolve_host_ips(hostname)

    # Validate all resolved IPs
    for ip_addr in resolved_ips:
        check_ip_is_public(ip_addr, url, blocked_ranges)

    # 2. Pin IPs for this thread
    pinned_map = _get_pinned_hosts()
    previous_entry = pinned_map.get(hostname)
    pinned_map[hostname] = resolved_ips

    logger.debug("Pinned DNS for %s: %s", hostname, resolved_ips)

    try:
        yield
    finally:
        # Restore previous state
        if previous_entry is None:
            if hostname in pinned_map:
                del pinned_map[hostname]
        else:
            pinned_map[hostname] = previous_entry

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import (
    Retrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500

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
    """Validate a URL to guard against SSRF attempts."""
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

    for ip_addr in _resolve_host_ips(parsed.hostname):
        _validate_ip_is_public(ip_addr, url, blocked_ranges)

    logger.info("URL validation passed for: %s", url)


def get_retry_decorator(
    max_attempts: int = 5,
    min_wait: float = 2.0,
    max_wait: float = 60.0,
    multiplier: float = 1.0,
) -> Any:
    """Get a tenacity retry decorator configured for network calls.

    Retries on:
    - httpx.HTTPError (except 4xx other than 429)
    - Connection errors

    Args:
        max_attempts: Maximum number of attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        multiplier: Exponential backoff multiplier

    Returns:
        A tenacity retry object

    """

    def is_retryable_error(exception: BaseException) -> bool:
        """Check if exception is retryable."""
        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            return status == HTTP_TOO_MANY_REQUESTS or status >= HTTP_SERVER_ERROR
        return isinstance(exception, (httpx.NetworkError, httpx.TimeoutException))

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(BaseException) & is_retryable_error,  # type: ignore
        reraise=True,
    )


def get_retrying_iterator(
    max_attempts: int = 5,
    min_wait: float = 2.0,
    max_wait: float = 60.0,
    multiplier: float = 1.0,
) -> Retrying:
    """Get a tenacity Retrying object for use in loops/contexts.

    Uses the same logic as get_retry_decorator.
    """

    def is_retryable_error(exception: BaseException) -> bool:
        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            return status == HTTP_TOO_MANY_REQUESTS or status >= HTTP_SERVER_ERROR
        return isinstance(exception, (httpx.NetworkError, httpx.TimeoutException))

    return Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(BaseException) & is_retryable_error,  # type: ignore
        reraise=True,
    )

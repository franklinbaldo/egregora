import socket
import pytest
from unittest.mock import patch
from egregora.security.dns import safe_dns_validation, SSRFValidationError

# Mock IP for safe.com
SAFE_IP = "93.184.216.34" # example.com
# Mock IP for evil.com
EVIL_IP = "127.0.0.1"

def mock_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "safe.com":
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (SAFE_IP, port or 80))]
    if host == "evil.com":
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (EVIL_IP, port or 80))]
    # Fallback for localhost etc if needed, though safe_dns_validation shouldn't be called on random things
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("0.0.0.0", 0))]

def test_redirect_ssrf_bypass():
    """Test that a redirect to a private IP is blocked by safe_dns_validation."""

    # We need to patch the _original_getaddrinfo used by egregora.security.dns
    with patch("egregora.security.dns._original_getaddrinfo", side_effect=mock_getaddrinfo):

        # We expect SSRFValidationError because the redirect to evil.com should be caught
        with pytest.raises(SSRFValidationError, match="resolves to blocked IP"):
            with safe_dns_validation("http://safe.com"):
                # Simulate httpx behavior

                # 1. Initial request to safe.com
                # safe_dns_validation resolves safe.com -> SAFE_IP (Public). Pins it.

                # 2. HTTP Client resolves safe.com
                # This goes through _pinned_getaddrinfo
                addr_info = socket.getaddrinfo("safe.com", 80)
                # Should return SAFE_IP
                assert addr_info[0][4][0] == SAFE_IP

                # 3. HTTP Client receives 301 to http://evil.com
                # 4. HTTP Client resolves evil.com
                # This goes through _pinned_getaddrinfo.
                # evil.com is NOT pinned.
                # CURRENT BEHAVIOR: Returns EVIL_IP (127.0.0.1)
                # DESIRED BEHAVIOR: Raises SSRFValidationError

                socket.getaddrinfo("evil.com", 80)

import socket
import uuid
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.avatar import download_avatar_from_url


def test_dns_rebinding_protection(tmp_path):
    """
    Verify DNS Rebinding protection.
    1. Validation check resolves 'evil.com' to 1.2.3.4 (Safe)
    2. Connection attempt SHOULD use the pinned IP (1.2.3.4) and NOT resolve again.

    If protected, we expect:
    - Only 1 call to the underlying DNS resolver (mocked).
    - Connection to 1.2.3.4.
    """
    safe_ip = "1.2.3.4"
    unsafe_ip = "127.0.0.1"

    # Counter for calls to the "upstream" DNS (mocked _original_getaddrinfo)
    evil_dns_calls = 0

    def side_effect(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
        nonlocal evil_dns_calls
        if host == "evil.com":
            evil_dns_calls += 1
            if evil_dns_calls == 1:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (safe_ip, port or 80))]
            # If we get here, pinning failed and it re-queried DNS
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (unsafe_ip, port or 80))]

        # Return empty for others to avoid side effects
        return []

    # Mock socket.socket for the connection attempt
    mock_socket_cls = MagicMock()
    mock_socket_instance = MagicMock()
    mock_socket_cls.return_value = mock_socket_instance

    def mock_connect(_addr):
        pass

    mock_socket_instance.connect.side_effect = mock_connect

    # Mock HTTP response so httpx is happy
    mock_socket_instance.sendall.return_value = None
    mock_socket_instance.recv.return_value = (
        b"HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\n\r\n" + b"\xff\xd8\xff"
    )

    # Patch _original_getaddrinfo in dns.py because that's what the patched socket.getaddrinfo calls
    with (
        patch("egregora.security.dns._original_getaddrinfo", side_effect=side_effect),
        patch("socket.socket", mock_socket_cls),
    ):
        try:
            download_avatar_from_url("http://evil.com/avatar.jpg", tmp_path, uuid.uuid4())
        except Exception:  # noqa: S110
            # Ignore exceptions unrelated to assertion logic
            pass

        connected_addresses = []
        for call in mock_socket_instance.connect.call_args_list:
            if call.args:
                connected_addresses.append(call.args[0][0])

        # Assertions

        if unsafe_ip in connected_addresses:
            pytest.fail(f"VULNERABILITY: Connected to unsafe IP {unsafe_ip}!")

        if safe_ip not in connected_addresses:
            pytest.fail(
                f"Did not connect to safe IP {safe_ip}. Pinning might be broken or connection failed."
            )

        # Verify cache usage
        if evil_dns_calls > 1:
            pytest.fail(
                f"DNS Pinning failed! Expected 1 DNS query, got {evil_dns_calls}. It re-resolved hostname."
            )

"""Unit test for rate_limit.py::get_client_ip -- a pure function (no DB, no
live server, no dependency on RATE_LIMITING_ENABLED) that the rest of this
suite never exercised directly: every other test here only proves rate
limiting end-to-end (via 429s against a live server), which requires
RATE_LIMITING_ENABLED=true and can't run in the same session as the rest of
the suite (which needs it off to avoid 429s from login-heavy runs). This
test needs neither -- it constructs a minimal Request-like object and calls
the function directly, so it always runs regardless of that env var.
"""
import os
import sys
from types import SimpleNamespace

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from auth import hash_api_key
from rate_limit import get_client_ip


def _request(headers):
    """A stand-in for the parts of a starlette Request that get_client_ip and
    get_remote_address touch: request.headers (dict-like, .get) and
    request.client.host (used by slowapi's get_remote_address fallback)."""
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host="203.0.113.9"))


class TestGetClientIp:
    def test_keys_by_api_key_hash_when_present(self):
        result = get_client_ip(_request({"x-api-key": "sk_test_key_1"}))
        assert result == f"apikey:{hash_api_key('sk_test_key_1')}"

    def test_different_api_keys_get_different_buckets(self):
        a = get_client_ip(_request({"x-api-key": "sk_test_key_1"}))
        b = get_client_ip(_request({"x-api-key": "sk_test_key_2"}))
        assert a != b

    def test_same_api_key_gets_same_bucket(self):
        a = get_client_ip(_request({"x-api-key": "sk_test_key_1"}))
        b = get_client_ip(_request({"x-api-key": "sk_test_key_1"}))
        assert a == b

    def test_never_puts_the_raw_key_in_the_bucket_key(self):
        result = get_client_ip(_request({"x-api-key": "sk_test_key_1"}))
        assert "sk_test_key_1" not in result

    def test_falls_back_to_x_real_ip_when_no_api_key(self):
        result = get_client_ip(_request({"x-real-ip": "198.51.100.7"}))
        assert result == "198.51.100.7"

    def test_falls_back_to_remote_address_when_no_api_key_or_real_ip(self):
        result = get_client_ip(_request({}))
        assert result == "203.0.113.9"

    def test_api_key_takes_priority_over_x_real_ip(self):
        result = get_client_ip(_request({"x-api-key": "sk_test_key_1", "x-real-ip": "198.51.100.7"}))
        assert result == f"apikey:{hash_api_key('sk_test_key_1')}"

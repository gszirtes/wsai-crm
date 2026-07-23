import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from auth import hash_api_key

_enabled = os.environ.get("RATE_LIMITING_ENABLED", "true").lower() == "true"


def get_client_ip(request):
    """Behind the nginx proxy (frontend/nginx.conf), every request's TCP peer
    is nginx itself, not the real client -- get_remote_address() alone would
    key every user's rate limit off the same address. nginx always sets
    X-Real-IP: $remote_addr itself (frontend/nginx.conf), which is its own
    direct view of the connecting socket and can't be overridden by a
    client-supplied header, unlike X-Forwarded-For (which a client can
    prefix with arbitrary values that a naive "take the first entry" reader
    would trust). Falls back to the raw peer address for direct/local access
    (e.g. hitting the backend on 127.0.0.1:8010 without going through nginx).

    Plan 6.3/audit A-7: an X-API-Key request (the MCP server, or any other
    service-account-authenticated caller) takes priority over IP entirely --
    every MCP call comes from the same container, so IP-keying would put
    every service account sharing that container into one bucket, letting
    one heavy caller starve every other API-key holder. Keyed on the key's
    hash (matching how it's stored), not the raw key, so no raw secret sits
    in the rate limiter's in-memory buckets.
    """
    api_key = request.headers.get("x-api-key")
    if api_key:
        return f"apikey:{hash_api_key(api_key)}"
    real_ip = request.headers.get("x-real-ip")
    return real_ip if real_ip else get_remote_address(request)


limiter = Limiter(key_func=get_client_ip, enabled=_enabled)

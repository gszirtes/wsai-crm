import os
from slowapi import Limiter
from slowapi.util import get_remote_address

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
    """
    real_ip = request.headers.get("x-real-ip")
    return real_ip if real_ip else get_remote_address(request)


limiter = Limiter(key_func=get_client_ip, enabled=_enabled)

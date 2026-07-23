"""Thin HTTP client for the CRM's own REST API (plan 6.1: the MCP server
talks to the backend over HTTP, never to the database directly, so every
business rule, capability check, and financial-masking dependency stays in
one place -- the backend -- instead of being reimplemented here).

Authenticates with a service account's X-API-Key (Phase 1). Whatever role/
capabilities an admin has assigned that service account in the capability
matrix apply automatically to every call this client makes -- there is no
separate authorization layer in the MCP server itself.
"""
import os
import httpx


class CrmApiError(Exception):
    """Raised for any non-2xx response, carrying the backend's own error
    detail so a calling tool can surface something useful to the agent
    instead of a bare HTTP status code."""

    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"CRM API error {status_code}: {detail}")


class CrmClient:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or os.environ["CRM_API_BASE_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["CRM_API_KEY"]
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    def _handle(self, r: httpx.Response):
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise CrmApiError(r.status_code, detail)
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    def get(self, path: str, params: dict = None):
        return self._handle(self._client.get(path, params=_clean(params)))

    def post(self, path: str, json: dict = None):
        return self._handle(self._client.post(path, json=json))

    def patch(self, path: str, json: dict = None):
        return self._handle(self._client.patch(path, json=json))

    def close(self):
        self._client.close()


def _clean(params: dict) -> dict:
    """Drop empty-string/None filter values so e.g. stage="" doesn't get
    sent as a literal empty-string query param (FastAPI would then filter
    on Deal.stage == "", matching nothing, instead of "no filter")."""
    if not params:
        return {}
    return {k: v for k, v in params.items() if v not in (None, "")}

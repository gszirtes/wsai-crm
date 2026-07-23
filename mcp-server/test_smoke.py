"""Smoke test for the MCP server, run against a LIVE stack (backend + this
server both up, backend seeded, a real service-account API key minted).

Not part of backend/tests/ pytest suite -- different protocol (MCP over
streamable HTTP, not plain REST), different service. This is the closest
equivalent to this repo's "integration tests against a live server"
philosophy for a service that speaks MCP instead of plain HTTP: it uses the
real MCP client protocol to call every tool through a live MCP server
connection, not a mocked one.

The CRM_API_KEY service account should have a role with view_financials,
manage_deals, manage_projects, and view_all_reports (e.g. "manager") --
several checks assert on values only visible with those capabilities.
ADMIN_EMAIL/ADMIN_PASSWORD (defaults: the seeded demo admin, matching
backend/tests/conftest.py) log in to mint two extra, disposable service
accounts used only to prove visibility/financial-masking actually apply
to MCP-tool calls, not just direct REST ones.

Usage:
    CRM_API_BASE_URL=http://localhost:8010 \
    CRM_API_KEY=sk_... \
    MCP_URL=http://localhost:8100/mcp \
    python test_smoke.py
"""
import asyncio
import json
import os
import sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8100/mcp")
CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL", "http://localhost:8010")
CRM_API_KEY = os.environ["CRM_API_KEY"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@wespeak.ai")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

EXPECTED_TOOLS = {
    "list_deals", "list_projects", "get_deal_detail", "get_project_detail",
    "get_deal_timeline", "get_deal_flow_report",
    "create_lead", "claim_deal", "change_deal_stage", "log_activity",
    "set_milestone_status",
}

_created_ids = {"deals": [], "companies": [], "contacts": [], "projects": [], "activities": []}


def rest_setup():
    """Create fixtures directly over REST (same API key) -- simpler than
    doing test setup through MCP tool calls, matches how backend/tests/
    already builds fixtures via the HTTP API rather than the DB."""
    client = httpx.Client(base_url=CRM_API_BASE_URL, headers={"X-API-Key": CRM_API_KEY})
    company = client.post("/api/companies", json={"name": "TEST_mcp smoke co"}).json()
    _created_ids["companies"].append(company["id"])
    project = client.post("/api/projects", json={
        "name": "TEST_mcp smoke project", "milestone_template": "milestones",
    }).json()
    _created_ids["projects"].append(project["id"])
    milestone = client.post(f"/api/projects/{project['id']}/milestones",
                            json={"name": "TEST_mcp smoke milestone", "amount": 100}).json()
    client.close()
    return company["id"], project["id"], milestone["id"]


def rest_cleanup():
    client = httpx.Client(base_url=CRM_API_BASE_URL, headers={"X-API-Key": CRM_API_KEY})
    for aid in _created_ids["activities"]:
        client.delete(f"/api/activities/{aid}")
    for did in _created_ids["deals"]:
        client.delete(f"/api/deals/{did}")
    for pid in _created_ids["projects"]:
        client.delete(f"/api/projects/{pid}")
    for cid in _created_ids["companies"]:
        client.delete(f"/api/companies/{cid}")
    client.close()


_admin_client = None
_extra_service_accounts = []


def rest_admin_login():
    """Cookie-authenticated client as the seeded admin -- only used to mint
    disposable, low-privilege service accounts for the visibility/masking
    checks below (service accounts can't create other service accounts;
    that route is admin-only)."""
    global _admin_client
    _admin_client = httpx.Client(base_url=CRM_API_BASE_URL)
    r = _admin_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return _admin_client


def mint_service_account(name: str, role: str) -> str:
    r = _admin_client.post("/api/service-accounts", json={"name": name, "role": role})
    r.raise_for_status()
    data = r.json()
    _extra_service_accounts.append(data["id"])
    return data["api_key"]


def rest_admin_cleanup():
    if _admin_client is None:
        return
    for sa_id in _extra_service_accounts:
        _admin_client.delete(f"/api/service-accounts/{sa_id}")
    _admin_client.close()


async def call(session: ClientSession, name: str, args: dict):
    import json
    result = await session.call_tool(name, args)
    if result.isError:
        raise RuntimeError(f"{name} failed: {result.content}")
    if result.structuredContent is not None:
        content = result.structuredContent
        # FastMCP wraps a non-object return value (e.g. a bare list[dict]) in
        # {"result": ...} since MCP's structured-output schema requires a
        # JSON object at the top level -- unwrap it so callers see the plain
        # value.
        if isinstance(content, dict) and set(content.keys()) == {"result"}:
            return content["result"]
        return content
    # No structured content (e.g. a tool return type FastMCP didn't infer a
    # schema for) -- fall back to parsing the plain-text content block,
    # which is always the JSON-encoded return value.
    return json.loads(result.content[0].text)


async def main():
    passed = []
    try:
        company_id, project_id, milestone_id = rest_setup()
        async with streamablehttp_client(MCP_URL, headers={"X-API-Key": CRM_API_KEY}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                missing = EXPECTED_TOOLS - names
                assert not missing, f"missing tools: {missing}"
                passed.append("list_tools: all 11 expected tools present")

                deals = await call(session, "list_deals", {})
                assert isinstance(deals, list)
                passed.append("list_deals: returned a list")

                projects = await call(session, "list_projects", {})
                assert isinstance(projects, list)
                passed.append("list_projects: returned a list")

                created = await call(session, "create_lead", {
                    "title": "TEST_mcp smoke lead", "value": 500, "company_id": company_id,
                })
                deal_id = created["id"]
                _created_ids["deals"].append(deal_id)
                assert created["owner_id"] is None, "service-account create must land unassigned"
                passed.append("create_lead: created, unassigned as expected")

                found = await call(session, "list_deals", {"search": "TEST_mcp smoke lead"})
                assert any(d["id"] == deal_id for d in found), "search should find the just-created deal by title"
                passed.append("list_deals: search param finds the created deal")

                found_projects = await call(session, "list_projects", {"search": "TEST_mcp smoke project"})
                assert any(p["id"] == project_id for p in found_projects), "search should find the setup project by name"
                passed.append("list_projects: search param finds the setup project")

                claim_result = await session.call_tool("claim_deal", {"deal_id": deal_id})
                assert claim_result.isError, "claim_deal must be rejected for a service account"
                passed.append("claim_deal: correctly rejected for service-account principal")

                staged = await call(session, "change_deal_stage", {"deal_id": deal_id, "stage": "qualified"})
                assert staged["stage"] == "qualified"
                passed.append("change_deal_stage: stage updated")

                detail = await call(session, "get_deal_detail", {"deal_id": deal_id})
                assert detail["deal"]["id"] == deal_id
                assert detail["deal"]["value"] == 500, "the setup account's role must have view_financials"
                passed.append("get_deal_detail: fetched, real value visible with view_financials")

                timeline = await call(session, "get_deal_timeline", {"deal_id": deal_id})
                assert isinstance(timeline, list) and len(timeline) >= 1
                passed.append("get_deal_timeline: has events")

                activity = await call(session, "log_activity", {
                    "subject": "TEST_mcp smoke activity", "type": "email",
                    "direction": "inbound", "deal_id": deal_id,
                })
                _created_ids["activities"].append(activity["id"])
                passed.append("log_activity: logged")

                deal_after = await call(session, "get_deal_detail", {"deal_id": deal_id})
                assert deal_after["deal"]["ball_in_court"] == "us", "inbound activity should set ball_in_court"
                passed.append("log_activity: ball_in_court updated automatically")

                flow = await call(session, "get_deal_flow_report", {})
                for key in ("won", "lost", "won_lost_ratio", "avg_passes_to_won", "avg_days_per_stage"):
                    assert key in flow, f"deal-flow report missing {key}"
                assert isinstance(flow["avg_days_per_stage"], dict)
                passed.append("get_deal_flow_report: full shape present (won/lost/ratio/passes/stage-days)")

                proj_detail = await call(session, "get_project_detail", {"project_id": project_id})
                assert proj_detail["project"]["id"] == project_id
                assert "health" in proj_detail and "logged_hours" in proj_detail and "billable_amount" in proj_detail
                passed.append("get_project_detail: fetched with health/hours/billing fields present")

                ms = await call(session, "set_milestone_status", {
                    "project_id": project_id, "milestone_id": milestone_id, "payment_status": "invoiced",
                })
                assert ms["payment_status"] == "invoiced"
                passed.append("set_milestone_status: updated")

        # -- Transport auth: the MCP server itself must reject a missing or
        # wrong X-API-Key before any MCP handshake even starts (the fix for
        # the audit's HIGH finding -- FastMCP mounts with no auth of its own
        # unless something wraps it). Plain HTTP, not the MCP client, since a
        # 401 happens before the protocol layer gets involved.
        for bad_headers, label in [({}, "missing"), ({"X-API-Key": "not-the-real-key"}, "wrong")]:
            r = httpx.post(MCP_URL, headers={
                **bad_headers,
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            assert r.status_code == 401, f"{label} X-API-Key should get 401, got {r.status_code}"
        passed.append("transport auth: missing/wrong X-API-Key rejected with 401")

        # -- Visibility isolation + financial masking. Proven at the REST
        # layer the MCP tools proxy to (crm_client.py adds no logic of its
        # own -- see server.py's docstring), not via a second MCP session:
        # the transport's ApiKeyAuthMiddleware gates the connection to the
        # ONE identity baked into this server's own CRM_API_KEY at startup
        # (that's the whole point of the auth fix above), so a differently
        # -privileged service account's key can never open an MCP session
        # against *this* running server at all -- only against the REST API
        # directly. What's actually testable, and what matters (per plan
        # 6.1: "identical to what a human user with that role would see"),
        # is that the REST responses these tools relay verbatim are
        # themselves visibility/masking-correct for a role that isn't this
        # server's own.
        rest_admin_login()
        try:
            main_client = httpx.Client(base_url=CRM_API_BASE_URL, headers={"X-API-Key": CRM_API_KEY})
            private_deal = main_client.post("/api/deals", json={
                "title": "TEST_mcp smoke private deal", "value": 999, "unassigned": True,
            }).json()
            private_deal_id = private_deal["id"]
            _created_ids["deals"].append(private_deal_id)
            vis = main_client.patch(f"/api/deals/{private_deal_id}/visibility", json={"visibility": "private"})
            vis.raise_for_status()
            main_client.close()

            # role="user" (not admin/manager -- those bypass visibility
            # entirely) with no EntityMembership row on the private deal.
            outsider_key = mint_service_account("TEST_mcp smoke outsider", "user")
            outsider_client = httpx.Client(base_url=CRM_API_BASE_URL, headers={"X-API-Key": outsider_key})
            outsider_resp = outsider_client.get(f"/api/deals/{private_deal_id}/detail")
            outsider_client.close()
            assert outsider_resp.status_code == 404, \
                "a non-member, non-admin/manager account must not see a private deal"
            passed.append("visibility: private deal invisible to a non-member account (REST layer the MCP tool proxies to)")

            # role="guest" -- D6: view_financials is off by default for guest.
            guest_key = mint_service_account("TEST_mcp smoke guest", "guest")
            guest_client = httpx.Client(base_url=CRM_API_BASE_URL, headers={"X-API-Key": guest_key})
            guest_detail = guest_client.get(f"/api/deals/{deal_id}/detail").json()
            guest_client.close()
            assert guest_detail["deal"]["value"] is None, "guest role (view_financials off) must see a masked value"
            passed.append("financial masking: guest-role account sees value: null (REST layer the MCP tool proxies to)")
        finally:
            rest_admin_cleanup()

    finally:
        rest_cleanup()

    print(f"\n{len(passed)} checks passed:")
    for p in passed:
        print(f"  - {p}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nSMOKE TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)

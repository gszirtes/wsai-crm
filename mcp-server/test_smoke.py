"""Smoke test for the MCP server, run against a LIVE stack (backend + this
server both up, backend seeded, a real service-account API key minted).

Not part of backend/tests/ pytest suite -- different protocol (MCP over
streamable HTTP, not plain REST), different service. This is the closest
equivalent to this repo's "integration tests against a live server"
philosophy for a service that speaks MCP instead of plain HTTP: it uses the
real MCP client protocol to call every tool through a live MCP server
connection, not a mocked one.

Usage:
    CRM_API_BASE_URL=http://localhost:8010 \
    CRM_API_KEY=sk_... \
    MCP_URL=http://localhost:8100/mcp \
    python test_smoke.py
"""
import asyncio
import os
import sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8100/mcp")
CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL", "http://localhost:8010")
CRM_API_KEY = os.environ["CRM_API_KEY"]

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
    company_id, project_id, milestone_id = rest_setup()
    passed = []
    try:
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

                claim_result = await session.call_tool("claim_deal", {"deal_id": deal_id})
                assert claim_result.isError, "claim_deal must be rejected for a service account"
                passed.append("claim_deal: correctly rejected for service-account principal")

                staged = await call(session, "change_deal_stage", {"deal_id": deal_id, "stage": "qualified"})
                assert staged["stage"] == "qualified"
                passed.append("change_deal_stage: stage updated")

                detail = await call(session, "get_deal_detail", {"deal_id": deal_id})
                assert detail["deal"]["id"] == deal_id
                passed.append("get_deal_detail: fetched")

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
                assert "won" in flow and "lost" in flow
                passed.append("get_deal_flow_report: shape OK")

                proj_detail = await call(session, "get_project_detail", {"project_id": project_id})
                assert proj_detail["project"]["id"] == project_id
                passed.append("get_project_detail: fetched")

                ms = await call(session, "set_milestone_status", {
                    "project_id": project_id, "milestone_id": milestone_id, "payment_status": "invoiced",
                })
                assert ms["payment_status"] == "invoiced"
                passed.append("set_milestone_status: updated")

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

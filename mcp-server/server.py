"""wespeak.ai CRM MCP server (plan Fazis 6).

Exposes a bounded set of CRM operations to an external AI agent over MCP,
authenticated as a Phase 1 ServiceAccount (X-API-Key). Every tool here is a
thin proxy to the CRM's own REST API (crm_client.py) -- no business rule,
capability check, or financial-masking logic is duplicated here. Whatever
role/capabilities an admin assigns the service account in the capability
matrix (Settings page) apply automatically to every tool call, exactly as
they would for a human user with that role.

Deliberately excludes delete, owner-reassignment, and visibility-change
tools (plan 6.3: least-privilege first tool set -- the plan's own tool list
names only the operations below; riskier writes are left for a later,
explicitly-scoped addition rather than exposed by default).
"""
import os
from mcp.server.fastmcp import FastMCP
from crm_client import CrmClient

mcp = FastMCP("wespeak-crm", host=os.environ.get("MCP_HOST", "0.0.0.0"),
              port=int(os.environ.get("MCP_PORT", "8100")))
crm = CrmClient()


# ---------- Read tools ----------

@mcp.tool()
def list_deals(stage: str = "", unassigned: bool = False) -> list[dict]:
    """List deals, optionally filtered by stage (lead/qualified/proposal/
    negotiation/won/lost) or unassigned=true for the shared-inbox leads
    with no owner. Private deals the calling service account isn't a
    member of are excluded, same as for any user. `value` is null unless
    the service account's role has view_financials."""
    return crm.get("/api/deals", params={"stage": stage, "unassigned": unassigned})


@mcp.tool()
def list_projects(status: str = "", limit: int = 20, offset: int = 0) -> list[dict]:
    """List projects, optionally filtered by status (planning/active/
    on_hold/completed/cancelled), paginated. `budget`/`hourly_rate` are
    null unless the service account's role has view_financials."""
    return crm.get("/api/projects", params={"status": status, "limit": limit, "offset": offset})


@mcp.tool()
def get_deal_detail(deal_id: str) -> dict:
    """Get a deal plus its company/contact names and activity timeline.
    Fails if the deal is private and the service account isn't a member."""
    return crm.get(f"/api/deals/{deal_id}/detail")


@mcp.tool()
def get_project_detail(project_id: str) -> dict:
    """Get a project plus time entries, milestones summary, billable
    amount, health, and activity timeline. Fails if the project is
    private and the service account isn't a member."""
    return crm.get(f"/api/projects/{project_id}/detail")


@mcp.tool()
def get_deal_timeline(deal_id: str) -> list[dict]:
    """Get a deal's chronological EventLog history (stage changes,
    ball-in-court passes, ownership changes, etc.)."""
    return crm.get(f"/api/deals/{deal_id}/timeline")


@mcp.tool()
def get_deal_flow_report() -> dict:
    """Get org-wide pipeline analytics: won/lost counts and ratio, average
    ball-in-court pass count to won, and average days spent per stage.
    Requires the service account's role to have view_all_reports."""
    return crm.get("/api/reports/deal-flow")


# ---------- Write tools ----------

@mcp.tool()
def create_lead(title: str, value: float = 0, currency: str = "EUR",
               company_id: str = None, contact_id: str = None, source: str = None) -> dict:
    """Create a new deal (lead). A service-account-authenticated create
    always lands unassigned in the shared inbox regardless of any
    unassigned flag, since owner_id is a FK to users.id and a service
    account has no row there -- a human claims it afterward via
    claim_deal or the app. Requires manage_deals."""
    return crm.post("/api/deals", json={
        "title": title, "value": value, "currency": currency,
        "company_id": company_id, "contact_id": contact_id, "source": source,
        "unassigned": True,
    })


@mcp.tool()
def claim_deal(deal_id: str) -> dict:
    """Claim an unassigned deal. NOTE: the CRM backend deliberately
    rejects this for a service-account principal (owner_id must be a real
    person for a claimed lead's "who's responsible" semantics to mean
    anything) -- this call will fail with a 400 explaining that. Kept as
    a tool because the plan names it in the base write set and a human
    reading the agent's transcript should see the backend's own rejection
    reason, not have the tool silently hidden."""
    return crm.post(f"/api/deals/{deal_id}/claim")


@mcp.tool()
def change_deal_stage(deal_id: str, stage: str) -> dict:
    """Move a deal to a new stage (lead/qualified/proposal/negotiation/
    won/lost). Recomputes probability automatically and logs a
    stage_changed event. Moving into won auto-creates a Project.
    Rejected if the deal has no owner and the target stage is past
    qualified. Requires manage_deals."""
    return crm.patch(f"/api/deals/{deal_id}/stage", json={"stage": stage})


@mcp.tool()
def log_activity(subject: str, type: str = "task", direction: str = None,
                 deal_id: str = None, project_id: str = None,
                 contact_id: str = None, company_id: str = None,
                 description: str = None, due_date: str = None) -> dict:
    """Log an activity (call/email/meeting/task/note). If linked to a
    deal_id with direction inbound/outbound, updates that deal's
    ball-in-court and last_contact_at automatically. due_date is an ISO
    8601 datetime string. Requires write access (non-guest)."""
    return crm.post("/api/activities", json={
        "subject": subject, "type": type, "direction": direction,
        "deal_id": deal_id, "project_id": project_id,
        "contact_id": contact_id, "company_id": company_id,
        "description": description, "due_date": due_date,
    })


@mcp.tool()
def set_milestone_status(project_id: str, milestone_id: str,
                         work_status: str = None, payment_status: str = None) -> dict:
    """Set a milestone's work_status (in_progress/client_review/accepted)
    and/or payment_status (not_due/invoiceable/invoiced/paid) -- pass
    either or both, independently settable and reversible. Requires
    manage_projects."""
    payload = {}
    if work_status:
        payload["work_status"] = work_status
    if payment_status:
        payload["payment_status"] = payment_status
    return crm.patch(f"/api/projects/{project_id}/milestones/{milestone_id}/status", json=payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

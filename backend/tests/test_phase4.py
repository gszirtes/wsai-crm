"""Phase 4 tests: milestones, HUF/EUR, deal->project automation, cash-flow.

Terv: INTEGRATION_PLAN.md "Fazis 4 - Merfoldkovek, rugalmas szamlazas,
deal->projekt automatizmus".
"""
import pytest


class TestCurrency:
    def test_invalid_deal_currency_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 bad currency", "currency": "USD"})
        assert r.status_code == 422

    def test_invalid_project_currency_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p4 bad currency", "currency": "USD"})
        assert r.status_code == 422


class TestMilestoneCRUD:
    def test_default_template_prefills_single_final(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p4 default template", "budget": 1000})
        p = r.json()
        try:
            listing = admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert len(listing["milestones"]) == 1
            assert listing["milestones"][0]["percentage"] == 100
            assert listing["total_amount"] == 1000
            assert listing["budget_mismatch"] is False
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_deposit_final_template(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 deposit template", "budget": 2000, "milestone_template": "deposit_final",
        })
        p = r.json()
        try:
            listing = admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert len(listing["milestones"]) == 2
            assert {m["name"] for m in listing["milestones"]} == {"Deposit", "Final delivery"}
            assert listing["total_amount"] == 2000
            # total_amount alone can't distinguish 50/50 from any other split
            # that happens to sum to 100% -- check each milestone's own share.
            by_name = {m["name"]: m["percentage"] for m in listing["milestones"]}
            assert by_name == {"Deposit": 50, "Final delivery": 50}
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_free_template_starts_empty(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 free template", "milestone_template": "milestones",
        })
        p = r.json()
        try:
            listing = admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert listing["milestones"] == []
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_create_milestone_with_amount(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 amount milestone", "milestone_template": "milestones",
        }).json()
        try:
            r = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 kickoff", "amount": 500,
            })
            assert r.status_code == 200, r.text
            m = r.json()
            assert m["amount"] == 500
            assert m["work_status"] == "in_progress"
            assert m["payment_status"] == "not_due"
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_amount_and_percentage_both_set_rejected(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 both set", "milestone_template": "milestones",
        }).json()
        try:
            r = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 bad", "amount": 100, "percentage": 50,
            })
            assert r.status_code == 422
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_amount_and_percentage_neither_set_rejected(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 neither set", "milestone_template": "milestones",
        }).json()
        try:
            r = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={"name": "TEST_p4 bad"})
            assert r.status_code == 422
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_amount_zero_and_percentage_zero_are_valid(self, admin_client, base_url):
        """amount/percentage=0 is falsy but a valid, distinct-from-None
        value (D11 is amount XOR percentage set, not truthy) -- a free
        milestone or a 0% placeholder must round-trip, not be rejected."""
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 zero values", "milestone_template": "milestones",
        }).json()
        try:
            r1 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 free", "amount": 0})
            assert r1.status_code == 200, r1.text
            assert r1.json()["amount"] == 0
            assert r1.json()["percentage"] is None
            r2 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 zero pct", "percentage": 0})
            assert r2.status_code == 200, r2.text
            assert r2.json()["percentage"] == 0
            assert r2.json()["amount"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_update_milestone(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 update milestone", "milestone_template": "milestones",
        }).json()
        try:
            m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 v1", "amount": 100,
            }).json()
            r = admin_client.put(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}", json={
                "name": "TEST_p4 v2", "amount": 200,
            })
            assert r.status_code == 200, r.text
            assert r.json()["name"] == "TEST_p4 v2"
            assert r.json()["amount"] == 200
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_update_milestone_switches_amount_to_percentage_and_back(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 switch mode", "milestone_template": "milestones",
        }).json()
        try:
            m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 switch", "amount": 100,
            }).json()
            r1 = admin_client.put(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}", json={
                "name": "TEST_p4 switch", "percentage": 40,
            })
            assert r1.status_code == 200, r1.text
            # Full-replace semantics: switching to percentage must null the
            # previously-set amount, not leave both populated.
            assert r1.json()["percentage"] == 40
            assert r1.json()["amount"] is None
            r2 = admin_client.put(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}", json={
                "name": "TEST_p4 switch", "amount": 300,
            })
            assert r2.status_code == 200, r2.text
            assert r2.json()["amount"] == 300
            assert r2.json()["percentage"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_delete_milestone(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 delete milestone", "milestone_template": "milestones",
        }).json()
        try:
            m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 doomed", "amount": 10,
            }).json()
            r = admin_client.delete(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}")
            assert r.status_code == 200, r.text
            listing = admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert listing["milestones"] == []
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_deleting_project_cascades_milestones(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 cascade delete", "milestone_template": "milestones",
        }).json()
        admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                          json={"name": "TEST_p4 cascade milestone", "amount": 1})
        r = admin_client.delete(f"{base_url}/api/projects/{p['id']}")
        assert r.status_code == 200, r.text
        # Project itself is gone, so the milestones sub-resource 404s rather
        # than returning an orphaned list -- proves the rows didn't survive.
        assert admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").status_code == 404

    def test_unrecognized_milestone_template_rejected_by_schema(self, admin_client, base_url):
        """milestone_templates.instantiate_template() has a fallback for an
        unrecognized template key, but ProjectCreate.milestone_template is a
        Pydantic Literal -- so that fallback is unreachable from the public
        API; a garbage value is rejected at the schema layer instead. This
        locks in the actual observable behavior."""
        r = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 garbage template", "milestone_template": "not_a_real_template",
        })
        assert r.status_code == 422

    def test_budget_mismatch_warning(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 mismatch", "budget": 1000, "milestone_template": "milestones",
        }).json()
        try:
            admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
                "name": "TEST_p4 partial", "amount": 400,
            })
            listing = admin_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert listing["total_amount"] == 400
            assert listing["budget_mismatch"] is True
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")


class TestMilestoneStatus:
    def _make_milestone(self, admin_client, base_url, name="TEST_p4 status milestone"):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": name, "milestone_template": "milestones",
        }).json()
        m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones", json={
            "name": name, "amount": 100,
        }).json()
        return p["id"], m["id"]

    def test_work_status_and_payment_status_independent(self, admin_client, base_url):
        project_id, milestone_id = self._make_milestone(admin_client, base_url)
        try:
            r = admin_client.patch(f"{base_url}/api/projects/{project_id}/milestones/{milestone_id}/status",
                                    json={"payment_status": "invoiced"})
            assert r.status_code == 200, r.text
            m = r.json()
            assert m["payment_status"] == "invoiced"
            assert m["work_status"] == "in_progress"  # untouched
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_status_reversible_both_directions(self, admin_client, base_url):
        project_id, milestone_id = self._make_milestone(admin_client, base_url, "TEST_p4 reversible")
        try:
            admin_client.patch(f"{base_url}/api/projects/{project_id}/milestones/{milestone_id}/status",
                               json={"work_status": "accepted"})
            r = admin_client.patch(f"{base_url}/api/projects/{project_id}/milestones/{milestone_id}/status",
                                    json={"work_status": "in_progress"})
            assert r.status_code == 200, r.text
            assert r.json()["work_status"] == "in_progress"
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_status_change_logs_event(self, admin_client, base_url):
        project_id, milestone_id = self._make_milestone(admin_client, base_url, "TEST_p4 logged")
        try:
            admin_client.patch(f"{base_url}/api/projects/{project_id}/milestones/{milestone_id}/status",
                               json={"payment_status": "invoiceable"})
            events = admin_client.get(f"{base_url}/api/event-logs",
                                      params={"entity_type": "milestone", "entity_id": milestone_id}).json()
            assert any(e["event_type"] == "status_changed" and e["to_value"] == "invoiceable" for e in events)
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")


class TestMilestoneVisibilityIDOR:
    def _private_project(self, admin_client, base_url, name="TEST_p4 private project"):
        p = admin_client.post(f"{base_url}/api/projects", json={"name": name}).json()
        r = admin_client.patch(f"{base_url}/api/projects/{p['id']}/visibility", json={"visibility": "private"})
        assert r.status_code == 200, r.text
        return p["id"]

    def test_list_milestones_404_for_non_member(self, admin_client, user_client, base_url):
        project_id = self._private_project(admin_client, base_url, "TEST_p4 private list")
        try:
            assert user_client.get(f"{base_url}/api/projects/{project_id}/milestones").status_code == 404
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_create_milestone_404_for_non_member(self, admin_client, user_client, base_url):
        project_id = self._private_project(admin_client, base_url, "TEST_p4 private create")
        try:
            r = user_client.post(f"{base_url}/api/projects/{project_id}/milestones",
                                 json={"name": "TEST_p4 sneaky", "amount": 1})
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_milestone_amount_masked_without_view_financials(self, admin_client, guest_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 masked", "budget": 500,
        }).json()
        try:
            listing = guest_client.get(f"{base_url}/api/projects/{p['id']}/milestones").json()
            assert listing["total_amount"] is None
            assert listing["budget"] is None
            assert all(m["amount"] is None for m in listing["milestones"] if m.get("percentage") is not None or True)
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")


class TestMilestoneCapability:
    """Milestone mutations are gated on manage_projects (the same capability
    Project CRUD itself uses), not plain require_write -- revoke it and
    confirm every mutating endpoint rejects a user who'd otherwise pass the
    project-visibility check, matching the established pattern in
    test_phase1.py::TestCapabilityMatrix."""

    def _without_manage_projects(self, admin_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        revoked = {**original, "user": {**original["user"], "manage_projects": False}}
        admin_client.put(f"{base_url}/api/settings/capabilities", json=revoked)
        return original

    def _restore(self, admin_client, base_url, original):
        admin_client.put(f"{base_url}/api/settings/capabilities", json=original)

    def test_revoking_manage_projects_blocks_all_milestone_mutations(self, admin_client, user_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 capability project", "milestone_template": "milestones",
        }).json()
        m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                              json={"name": "TEST_p4 capability milestone", "amount": 1}).json()
        original = self._without_manage_projects(admin_client, base_url)
        try:
            assert user_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                    json={"name": "TEST_p4 blocked", "amount": 1}).status_code == 403
            assert user_client.put(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}",
                                   json={"name": "TEST_p4 blocked", "amount": 2}).status_code == 403
            assert user_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}/status",
                                     json={"payment_status": "invoiceable"}).status_code == 403
            assert user_client.delete(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}").status_code == 403
        finally:
            self._restore(admin_client, base_url, original)
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")


class TestCashFlow:
    def test_invoiced_not_paid_counted_paid_excluded(self, admin_client, base_url):
        before = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["HUF"]
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 cashflow", "budget": 1000, "currency": "HUF", "milestone_template": "milestones",
        }).json()
        try:
            m1 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 cf invoiced", "amount": 300}).json()
            m2 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 cf paid", "amount": 700}).json()
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m1['id']}/status",
                               json={"payment_status": "invoiced"})
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m2['id']}/status",
                               json={"payment_status": "paid"})

            after = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["HUF"]
            # Exact delta, not >=: proves the paid (700) milestone is
            # genuinely excluded, not just that invoiced (300) is included.
            assert round(after - before, 2) == 300
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_percentage_milestone_counted_via_resolved_amount(self, admin_client, base_url):
        before = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["EUR"]
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 cashflow percentage", "budget": 2000, "milestone_template": "milestones",
        }).json()
        try:
            m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                  json={"name": "TEST_p4 cf pct", "percentage": 25}).json()
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}/status",
                               json={"payment_status": "invoiced"})
            after = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["EUR"]
            # 25% of a 2000 budget = 500, same resolved_milestone_amount()
            # helper the budget-mismatch warning uses.
            assert round(after - before, 2) == 500
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_work_status_independent_of_cash_flow_counting(self, admin_client, base_url):
        before = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["EUR"]
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 cashflow work status", "milestone_template": "milestones",
        }).json()
        try:
            m = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                  json={"name": "TEST_p4 cf work status", "amount": 150}).json()
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m['id']}/status",
                               json={"work_status": "accepted", "payment_status": "invoiced"})
            after = admin_client.get(f"{base_url}/api/dashboard/stats").json()["cash_flow_by_currency"]["EUR"]
            assert round(after - before, 2) == 150
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_cash_flow_masked_without_view_financials(self, admin_client, guest_client, base_url):
        stats = guest_client.get(f"{base_url}/api/dashboard/stats").json()
        assert stats["cash_flow_by_currency"] is None


class TestDealToProjectAutomation:
    def _project_for_deal(self, admin_client, base_url, deal_id):
        projects = admin_client.get(f"{base_url}/api/projects", params={"limit": 100}).json()
        matches = [p for p in projects if p.get("deal_id") == deal_id]
        return matches[0] if matches else None

    def test_won_with_no_company_or_contact_nulls_propagate(self, admin_client, base_url):
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 no company deal", "value": 10}).json()
        assert d["company_id"] is None and d["contact_id"] is None
        project_id = None
        try:
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            p = self._project_for_deal(admin_client, base_url, d["id"])
            assert p is not None
            project_id = p["id"]
            assert p["company_id"] is None
            assert p["contact_id"] is None
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_won_creates_project_with_copied_fields(self, admin_client, base_url):
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p4 auto co"}).json()
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p4 auto contact"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={
            "title": "TEST_p4 auto deal", "value": 5000, "currency": "HUF",
            "company_id": company["id"], "contact_id": contact["id"],
        }).json()
        project_id = None
        try:
            r = admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            assert r.status_code == 200, r.text
            p = self._project_for_deal(admin_client, base_url, d["id"])
            assert p is not None
            project_id = p["id"]
            assert p["name"] == "TEST_p4 auto deal"
            assert p["budget"] == 5000
            assert p["currency"] == "HUF"
            assert p["company_id"] == company["id"]
            assert p["contact_id"] == contact["id"]
            listing = admin_client.get(f"{base_url}/api/projects/{project_id}/milestones").json()
            assert len(listing["milestones"]) == 1
            assert listing["milestones"][0]["percentage"] == 100
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")
            admin_client.delete(f"{base_url}/api/companies/{company['id']}")
            admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")

    def test_put_to_won_creates_project(self, admin_client, base_url):
        """update_deal (PUT) has its own copy of the won-transition hook,
        separate from PATCH /stage -- this exercises that path directly
        rather than assuming it behaves like PATCH."""
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 put won deal", "value": 250}).json()
        project_id = None
        try:
            payload = {**{k: d[k] for k in ("title", "value", "currency", "probability",
                                            "expected_close", "notes", "company_id", "contact_id", "source")},
                      "stage": "won"}
            r = admin_client.put(f"{base_url}/api/deals/{d['id']}", json=payload)
            assert r.status_code == 200, r.text
            p = self._project_for_deal(admin_client, base_url, d["id"])
            assert p is not None
            project_id = p["id"]
            assert p["budget"] == 250
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_put_while_already_won_does_not_duplicate_project(self, admin_client, base_url):
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 put no-op deal", "value": 50}).json()
        project_id = None
        try:
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            d = admin_client.get(f"{base_url}/api/deals/{d['id']}").json()
            payload = {**{k: d[k] for k in ("value", "currency", "probability", "expected_close", "notes",
                                            "company_id", "contact_id", "source")},
                      "title": "TEST_p4 put no-op deal renamed", "stage": "won"}
            r = admin_client.put(f"{base_url}/api/deals/{d['id']}", json=payload)
            assert r.status_code == 200, r.text
            assert r.json()["title"] == "TEST_p4 put no-op deal renamed"
            projects = admin_client.get(f"{base_url}/api/projects", params={"limit": 100}).json()
            matches = [p for p in projects if p.get("deal_id") == d["id"]]
            assert len(matches) == 1
            project_id = matches[0]["id"]
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_won_transition_is_idempotent(self, admin_client, base_url):
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 idempotent deal", "value": 100}).json()
        project_id = None
        try:
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "lost"})
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            projects = admin_client.get(f"{base_url}/api/projects", params={"limit": 100}).json()
            matches = [p for p in projects if p.get("deal_id") == d["id"]]
            assert len(matches) == 1
            project_id = matches[0]["id"]
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_double_lead_type_project_bills_contract_company(self, admin_client, base_url):
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p4 day-to-day co"}).json()
        contract_company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p4 contract co"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={
            "title": "TEST_p4 double auto deal", "value": 1000, "lead_type": "double",
            "company_id": company["id"], "contract_company_id": contract_company["id"],
        }).json()
        project_id = None
        try:
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            p = self._project_for_deal(admin_client, base_url, d["id"])
            assert p is not None
            project_id = p["id"]
            assert p["company_id"] == contract_company["id"]
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")
            admin_client.delete(f"{base_url}/api/companies/{company['id']}")
            admin_client.delete(f"{base_url}/api/companies/{contract_company['id']}")

    def test_private_deal_membership_carries_over_to_spawned_project(self, admin_client, user_client, base_url):
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p4 private auto deal", "value": 1}).json()
        project_id = None
        try:
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/visibility", json={"visibility": "private"})
            user_id = user_client.get(f"{base_url}/api/auth/me").json()["id"]
            admin_client.post(f"{base_url}/api/deals/{d['id']}/members", json={"user_id": user_id})
            admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            p = self._project_for_deal(admin_client, base_url, d["id"])
            assert p is not None
            project_id = p["id"]
            assert p["visibility"] == "private"
            assert user_client.get(f"{base_url}/api/projects/{project_id}").status_code == 200
        finally:
            if project_id:
                admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

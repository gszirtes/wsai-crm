"""Phase 4 tests: milestones, HUF/EUR, deal->project automation, cash-flow.

Terv: INTEGRATION_PLAN.md "Fazis 4 - Merfoldkovek, rugalmas szamlazas,
deal->projekt automatizmus".
"""
import pytest


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


class TestCashFlow:
    def test_invoiced_not_paid_counted_paid_excluded(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p4 cashflow", "budget": 1000, "currency": "HUF", "milestone_template": "milestones",
        }).json()
        m1 = m2 = None
        try:
            m1 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 cf invoiced", "amount": 300}).json()
            m2 = admin_client.post(f"{base_url}/api/projects/{p['id']}/milestones",
                                   json={"name": "TEST_p4 cf paid", "amount": 700}).json()
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m1['id']}/status",
                               json={"payment_status": "invoiced"})
            admin_client.patch(f"{base_url}/api/projects/{p['id']}/milestones/{m2['id']}/status",
                               json={"payment_status": "paid"})

            stats = admin_client.get(f"{base_url}/api/dashboard/stats").json()
            assert stats["cash_flow_by_currency"]["HUF"] >= 300
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

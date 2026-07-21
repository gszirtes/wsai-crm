"""Phase 2 tests: lead ownership/claim, ball-in-court, timeline + analytics.

Terv: INTEGRATION_PLAN.md "Fazis 2 - Lead-tulajdon + labda-status + eletut".
"""
import pytest


def _events(client, base_url, entity_type, entity_id):
    r = client.get(f"{base_url}/api/event-logs",
                   params={"entity_type": entity_type, "entity_id": entity_id})
    assert r.status_code == 200, r.text
    return r.json()


class TestClaim:
    """2.1: unassigned create-time flag, claim endpoint, owner-required
    stage guard (D1/BL-4), owner reassignment (reassign_owner)."""

    def test_default_create_owner_is_creator(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 owned"})
        d = r.json()
        try:
            assert d["owner_id"] is not None
            assert d["claimed_at"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_unassigned_create_has_no_owner(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 unassigned", "unassigned": True})
        d = r.json()
        try:
            assert d["owner_id"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_deal_source_round_trips(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 source", "source": "referral"})
        d = r.json()
        try:
            assert d["source"] == "referral"
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_invalid_source_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 bad source", "source": "bogus"})
        assert r.status_code == 422

    def test_cannot_advance_past_qualified_without_owner(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 guard", "unassigned": True})
        deal_id = r.json()["id"]
        try:
            pr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/stage", json={"stage": "proposal"})
            assert pr.status_code == 400, pr.text
            # qualified itself is still allowed unowned
            qr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/stage", json={"stage": "qualified"})
            assert qr.status_code == 200, qr.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_put_also_enforces_owner_guard(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 put guard", "unassigned": True})
        d = r.json()
        try:
            payload = {**{k: d[k] for k in ("title", "value", "currency", "probability",
                                            "expected_close", "notes", "company_id", "contact_id", "source")},
                      "stage": "won"}
            pr = admin_client.put(f"{base_url}/api/deals/{d['id']}", json=payload)
            assert pr.status_code == 400, pr.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_claim_sets_owner_and_claimed_at_and_logs(self, admin_client, user_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 claim", "unassigned": True})
        deal_id = r.json()["id"]
        try:
            cr = user_client.patch(f"{base_url}/api/deals/{deal_id}/claim")
            assert cr.status_code == 200, cr.text
            body = cr.json()
            assert body["owner_id"] is not None
            assert body["claimed_at"] is not None
            events = _events(admin_client, base_url, "deal", deal_id)
            claimed = [e for e in events if e["event_type"] == "claimed"]
            assert len(claimed) == 1
            # claiming unblocks advancing past qualified
            sr = user_client.patch(f"{base_url}/api/deals/{deal_id}/stage", json={"stage": "proposal"})
            assert sr.status_code == 200, sr.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_claim_already_owned_deal_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 already owned"})
        deal_id = r.json()["id"]
        try:
            cr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/claim")
            assert cr.status_code == 400
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_unassigned_filter_excludes_owned_deals(self, admin_client, base_url):
        owned = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 filter owned"}).json()
        unassigned = admin_client.post(f"{base_url}/api/deals",
                                       json={"title": "TEST_p2 filter unassigned", "unassigned": True}).json()
        try:
            ids = [d["id"] for d in admin_client.get(f"{base_url}/api/deals", params={"unassigned": "true"}).json()]
            assert unassigned["id"] in ids
            assert owned["id"] not in ids
        finally:
            admin_client.delete(f"{base_url}/api/deals/{owned['id']}")
            admin_client.delete(f"{base_url}/api/deals/{unassigned['id']}")

    def test_reassign_owner_requires_capability(self, admin_client, user_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 reassign perm"}).json()
        try:
            r = user_client.get(f"{base_url}/api/users/directory")
            other_user_id = [u for u in r.json() if u["email"] == "manager@wespeak.ai"][0]["id"]
            # user role defaults to reassign_owner=False
            fr = user_client.patch(f"{base_url}/api/deals/{d['id']}/owner", json={"owner_id": other_user_id})
            assert fr.status_code == 403, fr.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)

    def test_reassign_owner_changes_owner_and_logs(self, admin_client, base_url):
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p2 reassign"}).json()
        try:
            r = admin_client.get(f"{base_url}/api/users/directory")
            target = [u for u in r.json() if u["email"] == "user@wespeak.ai"][0]
            rr = admin_client.patch(f"{base_url}/api/deals/{d['id']}/owner", json={"owner_id": target["id"]})
            assert rr.status_code == 200, rr.text
            assert rr.json()["owner_id"] == target["id"]
            events = _events(admin_client, base_url, "deal", d["id"])
            changed = [e for e in events if e["event_type"] == "owner_changed"]
            assert len(changed) == 1
            assert changed[0]["to_value"] == target["id"]
            members = admin_client.get(f"{base_url}/api/deals/{d['id']}/members").json()
            assert target["id"] in [m["user_id"] for m in members]
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")


class TestUnclaimedLeadReminder:
    """2.1: auto_unclaimed_lead surfaces to view_all_reports-capable users
    (managers/admin), threshold is D7's admin-configurable unassigned_days."""

    def test_unclaimed_lead_notification_after_threshold(self, admin_client, manager_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/thresholds").json()
        d = admin_client.post(f"{base_url}/api/deals",
                              json={"title": "TEST_p2 unclaimed notif", "unassigned": True}).json()
        try:
            admin_client.put(f"{base_url}/api/settings/thresholds", json={**original, "unassigned_days": 0})
            notifs = manager_client.get(f"{base_url}/api/notifications").json()
            keys = [n["type"] for n in notifs["items"] if d["title"] in (n["body"] or "")]
            assert "auto_unclaimed_lead" in keys
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_no_unclaimed_lead_notification_before_threshold(self, admin_client, manager_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/thresholds").json()
        d = admin_client.post(f"{base_url}/api/deals",
                              json={"title": "TEST_p2 unclaimed no notif", "unassigned": True}).json()
        try:
            admin_client.put(f"{base_url}/api/settings/thresholds", json={**original, "unassigned_days": 999})
            notifs = manager_client.get(f"{base_url}/api/notifications").json()
            bodies = [n["body"] for n in notifs["items"] if n["type"] == "auto_unclaimed_lead"]
            assert d["title"] not in bodies
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_non_manager_does_not_see_unclaimed_lead_notification(self, admin_client, user_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/thresholds").json()
        d = admin_client.post(f"{base_url}/api/deals",
                              json={"title": "TEST_p2 unclaimed user bell", "unassigned": True}).json()
        try:
            admin_client.put(f"{base_url}/api/settings/thresholds", json={**original, "unassigned_days": 0})
            notifs = user_client.get(f"{base_url}/api/notifications").json()
            bodies = [n["body"] for n in notifs["items"] if n["type"] == "auto_unclaimed_lead"]
            assert d["title"] not in bodies
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

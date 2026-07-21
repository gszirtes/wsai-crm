"""Phase 1 tests: access control (capability matrix, visibility, membership,
financial masking, service accounts), plus a couple of Phase 0 gaps caught
during this phase's own review (deleted events, PUT-completed-change logging)."""
import pytest


def _events(client, base_url, entity_type, entity_id):
    r = client.get(f"{base_url}/api/event-logs",
                   params={"entity_type": entity_type, "entity_id": entity_id})
    assert r.status_code == 200, r.text
    return r.json()


class TestDeletedEventPhase0Gap:
    """Phase 0 wired log_event() into create/status/stage paths but not delete
    -- caught during Phase 1's own re-review of Phase 0, per the plan's
    "every write path logs" mandate. Covers all 5 owner_id-bearing entities."""

    def test_delete_company_logs_deleted_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p1 delete co"})
        company_id = cr.json()["id"]
        admin_client.delete(f"{base_url}/api/companies/{company_id}")
        events = _events(admin_client, base_url, "company", company_id)
        assert [e for e in events if e["event_type"] == "deleted"]

    def test_delete_contact_logs_deleted_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p1_delete"})
        contact_id = cr.json()["id"]
        admin_client.delete(f"{base_url}/api/contacts/{contact_id}")
        events = _events(admin_client, base_url, "contact", contact_id)
        assert [e for e in events if e["event_type"] == "deleted"]

    def test_delete_deal_logs_deleted_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 delete deal"})
        deal_id = cr.json()["id"]
        admin_client.delete(f"{base_url}/api/deals/{deal_id}")
        events = _events(admin_client, base_url, "deal", deal_id)
        assert [e for e in events if e["event_type"] == "deleted"]

    def test_delete_project_logs_deleted_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p1 delete proj"})
        project_id = cr.json()["id"]
        admin_client.delete(f"{base_url}/api/projects/{project_id}")
        events = _events(admin_client, base_url, "project", project_id)
        assert [e for e in events if e["event_type"] == "deleted"]

    def test_delete_activity_logs_deleted_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p1 delete activity",
        })
        activity_id = cr.json()["id"]
        admin_client.delete(f"{base_url}/api/activities/{activity_id}")
        events = _events(admin_client, base_url, "activity", activity_id)
        assert [e for e in events if e["event_type"] == "deleted"]


class TestActivityPutCompletedChangePhase0Gap:
    """PATCH /toggle logged status_changed from Phase 0 on; a full PUT that
    also flips `completed` did not -- same gap, fixed alongside `deleted`."""

    def test_put_changing_completed_logs_status_changed(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p1 put completed",
        })
        a = cr.json()
        try:
            ur = admin_client.put(f"{base_url}/api/activities/{a['id']}", json={
                **{k: a[k] for k in ("type", "direction", "subject", "description",
                                     "due_date", "contact_id", "company_id", "deal_id", "project_id")},
                "completed": True,
            })
            assert ur.status_code == 200, ur.text
            events = _events(admin_client, base_url, "activity", a["id"])
            status_events = [e for e in events if e["event_type"] == "status_changed"]
            assert len(status_events) == 1
            assert status_events[0]["from_value"] == "False"
            assert status_events[0]["to_value"] == "True"
        finally:
            admin_client.delete(f"{base_url}/api/activities/{a['id']}")

    def test_put_not_changing_completed_logs_nothing(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p1 put no change",
        })
        a = cr.json()
        try:
            ur = admin_client.put(f"{base_url}/api/activities/{a['id']}", json={
                **{k: a[k] for k in ("type", "direction", "subject", "description",
                                     "due_date", "contact_id", "company_id", "deal_id", "project_id")},
                "completed": False,
            })
            assert ur.status_code == 200, ur.text
            events = _events(admin_client, base_url, "activity", a["id"])
            assert not [e for e in events if e["event_type"] == "status_changed"]
        finally:
            admin_client.delete(f"{base_url}/api/activities/{a['id']}")


class TestCapabilityMatrix:
    def test_get_capabilities_admin_only(self, user_client, guest_client, base_url):
        for client in (user_client, guest_client):
            r = client.get(f"{base_url}/api/settings/capabilities")
            assert r.status_code == 403

    def test_get_capabilities_defaults(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/settings/capabilities")
        assert r.status_code == 200, r.text
        m = r.json()
        for role in ("admin", "manager"):
            assert all(m[role].values()), f"{role} should default to all capabilities true"
        assert m["guest"]["view_financials"] is False
        assert m["user"]["manage_deals"] is True

    def test_put_capabilities_requires_full_matrix(self, admin_client, base_url):
        r = admin_client.put(f"{base_url}/api/settings/capabilities", json={"admin": {"view_financials": True}})
        assert r.status_code == 422

    def test_put_capabilities_non_admin_forbidden(self, admin_client, user_client, base_url):
        current = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        r = user_client.put(f"{base_url}/api/settings/capabilities", json=current)
        assert r.status_code == 403

    def test_revoking_manage_deals_blocks_user_then_restoring_allows_again(self, admin_client, user_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            revoked = json_copy = {**original, "user": {**original["user"], "manage_deals": False}}
            pr = admin_client.put(f"{base_url}/api/settings/capabilities", json=revoked)
            assert pr.status_code == 200, pr.text

            r = user_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 should be blocked"})
            assert r.status_code == 403, r.text
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)

        r = user_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 restored"})
        assert r.status_code == 200, r.text
        admin_client.delete(f"{base_url}/api/deals/{r.json()['id']}")

    def test_view_all_reports_capability_gates_utilization(self, admin_client, user_client, base_url):
        # Default: user lacks view_all_reports -> 403 (unchanged behavior from require_role("manager"))
        r = user_client.get(f"{base_url}/api/reports/utilization")
        assert r.status_code == 403
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            granted = {**original, "user": {**original["user"], "view_all_reports": True}}
            admin_client.put(f"{base_url}/api/settings/capabilities", json=granted)
            r = user_client.get(f"{base_url}/api/reports/utilization")
            assert r.status_code == 200, r.text
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)


class TestVisibility:
    def test_new_deal_defaults_to_public(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 vis deal"})
        assert r.status_code == 200, r.text
        assert r.json()["visibility"] == "public"
        admin_client.delete(f"{base_url}/api/deals/{r.json()['id']}")

    def test_new_project_defaults_to_public(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p1 vis project"})
        assert r.status_code == 200, r.text
        assert r.json()["visibility"] == "public"
        admin_client.delete(f"{base_url}/api/projects/{r.json()['id']}")

    def test_org_default_visibility_setting(self, admin_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings").json()["default_visibility"]
        try:
            pr = admin_client.put(f"{base_url}/api/settings", json={"default_visibility": "private"})
            assert pr.status_code == 200, pr.text
            assert pr.json()["default_visibility"] == "private"
            r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 default private"})
            assert r.json()["visibility"] == "private"
            admin_client.delete(f"{base_url}/api/deals/{r.json()['id']}")
        finally:
            admin_client.put(f"{base_url}/api/settings", json={"default_visibility": original})

    def test_patch_visibility_logs_event_and_persists(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 patch vis"})
        deal_id = r.json()["id"]
        try:
            pr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/visibility", json={"visibility": "private"})
            assert pr.status_code == 200, pr.text
            assert pr.json()["visibility"] == "private"
            events = _events(admin_client, base_url, "deal", deal_id)
            vis_events = [e for e in events if e["event_type"] == "visibility_changed"]
            assert len(vis_events) == 1
            assert vis_events[0]["from_value"] == "public"
            assert vis_events[0]["to_value"] == "private"
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_patch_visibility_invalid_value_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 bad vis"})
        deal_id = r.json()["id"]
        try:
            pr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/visibility", json={"visibility": "hidden"})
            assert pr.status_code == 422
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_guest_cannot_change_visibility(self, admin_client, guest_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 guest vis"})
        deal_id = r.json()["id"]
        try:
            pr = guest_client.patch(f"{base_url}/api/deals/{deal_id}/visibility", json={"visibility": "private"})
            assert pr.status_code == 403
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_put_deal_cannot_silently_change_visibility(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 put vis"})
        deal_id = r.json()["id"]
        try:
            ur = admin_client.put(f"{base_url}/api/deals/{deal_id}", json={
                "title": "TEST_p1 put vis", "visibility": "private",
            })
            assert ur.status_code == 200, ur.text
            assert ur.json()["visibility"] == "public", "PUT must not be able to change visibility"
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")


class TestEntityMembership:
    def _other_user_id(self, admin_client, base_url, email):
        r = admin_client.get(f"{base_url}/api/users/directory")
        assert r.status_code == 200, r.text
        match = [u for u in r.json() if u["email"] == email]
        assert match, f"seeded user {email} not found in directory"
        return match[0]["id"]

    def test_owner_auto_member_on_create(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 auto member"})
        deal_id = r.json()["id"]
        owner_id = r.json()["owner_id"]
        try:
            mr = admin_client.get(f"{base_url}/api/deals/{deal_id}/members")
            assert mr.status_code == 200, mr.text
            assert [m for m in mr.json() if m["user_id"] == owner_id]
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_directory_available_to_non_admin(self, user_client, base_url):
        r = user_client.get(f"{base_url}/api/users/directory")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)
        assert "role" not in r.json()[0]

    def test_invite_and_remove_project_member(self, admin_client, base_url):
        user_id = self._other_user_id(admin_client, base_url, "manager@wespeak.ai")
        r = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p1 invite project"})
        project_id = r.json()["id"]
        try:
            ir = admin_client.post(f"{base_url}/api/projects/{project_id}/members", json={"user_id": user_id})
            assert ir.status_code == 200, ir.text
            mr = admin_client.get(f"{base_url}/api/projects/{project_id}/members").json()
            assert [m for m in mr if m["user_id"] == user_id]

            dr = admin_client.delete(f"{base_url}/api/projects/{project_id}/members/{user_id}")
            assert dr.status_code == 200, dr.text
            mr2 = admin_client.get(f"{base_url}/api/projects/{project_id}/members").json()
            assert not [m for m in mr2 if m["user_id"] == user_id]
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_cannot_remove_owner_from_membership(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 owner protect"})
        deal_id = r.json()["id"]
        owner_id = r.json()["owner_id"]
        try:
            dr = admin_client.delete(f"{base_url}/api/deals/{deal_id}/members/{owner_id}")
            assert dr.status_code == 400
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_invite_requires_invite_members_capability(self, admin_client, user_client, base_url):
        user_id = self._other_user_id(admin_client, base_url, "guest@wespeak.ai")
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 cap gate"})
        deal_id = r.json()["id"]
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            revoked = {**original, "user": {**original["user"], "invite_members": False}}
            admin_client.put(f"{base_url}/api/settings/capabilities", json=revoked)
            ir = user_client.post(f"{base_url}/api/deals/{deal_id}/members", json={"user_id": user_id})
            assert ir.status_code == 403
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_invite_nonexistent_user_404(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p1 bad invite"})
        deal_id = r.json()["id"]
        try:
            ir = admin_client.post(f"{base_url}/api/deals/{deal_id}/members", json={"user_id": "does-not-exist"})
            assert ir.status_code == 404
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

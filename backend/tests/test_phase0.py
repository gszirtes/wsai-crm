"""Phase 0 tests: Alembic-owned schema stays intact, Activity.direction field."""
import pytest


class TestActivityDirection:
    def _get_or_create_contact(self, client, base_url):
        r = client.get(f"{base_url}/api/contacts")
        assert r.status_code == 200
        contacts = r.json()
        if contacts:
            return contacts[0]["id"], False
        r = client.post(f"{base_url}/api/contacts", json={
            "first_name": "TEST_p0", "last_name": "Direction", "email": "test_p0@example.com",
            "status": "lead",
        })
        assert r.status_code == 200
        return r.json()["id"], True

    def _get_or_create_deal(self, client, base_url):
        r = client.get(f"{base_url}/api/deals")
        assert r.status_code == 200
        deals = r.json()
        if deals:
            return deals[0]["id"]
        r = client.post(f"{base_url}/api/deals", json={"title": "TEST_p0 deal"})
        assert r.status_code == 200
        return r.json()["id"]

    def test_direction_round_trips_on_contact_activity(self, admin_client, base_url):
        contact_id, created = self._get_or_create_contact(admin_client, base_url)
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "email", "direction": "inbound",
            "subject": "TEST_p0 inbound email", "contact_id": contact_id,
        })
        assert cr.status_code == 200, cr.text
        assert cr.json()["direction"] == "inbound"
        activity_id = cr.json()["id"]
        try:
            dr = admin_client.get(f"{base_url}/api/contacts/{contact_id}/detail")
            assert dr.status_code == 200
            match = [a for a in dr.json()["activities"] if a["id"] == activity_id]
            assert match and match[0]["direction"] == "inbound"
        finally:
            admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            if created:
                admin_client.delete(f"{base_url}/api/contacts/{contact_id}")

    def test_direction_round_trips_on_deal_activity(self, admin_client, base_url):
        deal_id = self._get_or_create_deal(admin_client, base_url)
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "call", "direction": "outbound",
            "subject": "TEST_p0 outbound call", "deal_id": deal_id,
        })
        assert cr.status_code == 200, cr.text
        activity_id = cr.json()["id"]
        try:
            dr = admin_client.get(f"{base_url}/api/deals/{deal_id}/detail")
            assert dr.status_code == 200
            match = [a for a in dr.json()["activities"] if a["id"] == activity_id]
            assert match and match[0]["direction"] == "outbound"
        finally:
            admin_client.delete(f"{base_url}/api/activities/{activity_id}")

    def test_direction_defaults_to_null(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p0 no direction",
        })
        assert cr.status_code == 200, cr.text
        assert cr.json()["direction"] is None
        admin_client.delete(f"{base_url}/api/activities/{cr.json()['id']}")

    def test_invalid_direction_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p0 bad direction", "direction": "sideways",
        })
        assert r.status_code == 422


class TestEventLog:
    def _events(self, client, base_url, entity_type, entity_id):
        r = client.get(f"{base_url}/api/event-logs",
                       params={"entity_type": entity_type, "entity_id": entity_id})
        assert r.status_code == 200, r.text
        return r.json()

    def test_create_deal_logs_created_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p0 event deal"})
        assert cr.status_code == 200, cr.text
        deal_id = cr.json()["id"]
        try:
            events = self._events(admin_client, base_url, "deal", deal_id)
            created = [e for e in events if e["event_type"] == "created"]
            assert len(created) == 1
            assert created[0]["actor_type"] == "user"
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_stage_change_logs_stage_changed_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p0 stage deal"})
        deal_id = cr.json()["id"]
        try:
            pr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/stage", json={"stage": "qualified"})
            assert pr.status_code == 200, pr.text
            events = self._events(admin_client, base_url, "deal", deal_id)
            stage_events = [e for e in events if e["event_type"] == "stage_changed"]
            assert len(stage_events) == 1
            assert stage_events[0]["from_value"] == "lead"
            assert stage_events[0]["to_value"] == "qualified"
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_same_stage_patch_does_not_log_duplicate_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p0 nochange deal"})
        deal_id = cr.json()["id"]
        try:
            admin_client.patch(f"{base_url}/api/deals/{deal_id}/stage", json={"stage": "lead"})
            events = self._events(admin_client, base_url, "deal", deal_id)
            assert not [e for e in events if e["event_type"] == "stage_changed"]
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_activity_on_deal_logs_activity_logged_event(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p0 activity deal"})
        deal_id = cr.json()["id"]
        try:
            ar = admin_client.post(f"{base_url}/api/activities", json={
                "type": "call", "subject": "TEST_p0 logged call", "deal_id": deal_id,
            })
            assert ar.status_code == 200, ar.text
            activity_id = ar.json()["id"]
            try:
                events = self._events(admin_client, base_url, "deal", deal_id)
                logged = [e for e in events if e["event_type"] == "activity_logged"]
                assert len(logged) == 1
                assert logged[0]["activity_id"] == activity_id
            finally:
                admin_client.delete(f"{base_url}/api/activities/{activity_id}")
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_activity_toggle_logs_status_changed_event(self, admin_client, base_url):
        ar = admin_client.post(f"{base_url}/api/activities", json={
            "type": "task", "subject": "TEST_p0 toggle me",
        })
        activity_id = ar.json()["id"]
        try:
            tr = admin_client.patch(f"{base_url}/api/activities/{activity_id}/toggle")
            assert tr.status_code == 200, tr.text
            events = self._events(admin_client, base_url, "activity", activity_id)
            status_events = [e for e in events if e["event_type"] == "status_changed"]
            assert len(status_events) == 1
            assert status_events[0]["from_value"] == "False"
            assert status_events[0]["to_value"] == "True"
        finally:
            admin_client.delete(f"{base_url}/api/activities/{activity_id}")

    def test_user_forbidden_from_event_logs(self, user_client, base_url):
        r = user_client.get(f"{base_url}/api/event-logs",
                            params={"entity_type": "deal", "entity_id": "anything"})
        assert r.status_code == 403


class TestSchemaHygiene:
    """0.4: Literal-typed enums reject invalid values with 422 instead of the
    old silent-fallback-to-default behavior, and every error response shares
    one envelope shape."""

    def test_invalid_role_on_create_rejected_not_fallback(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/users", json={
            "email": f"test_p0_badrole_{id(self)}@example.com",
            "password": "secret123", "name": "Bad Role", "role": "superadmin",
        })
        assert r.status_code == 422, r.text

    def test_invalid_role_on_update_rejected(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/users")
        target = next(u for u in r.json() if u["email"] == "user@wespeak.ai")
        r = admin_client.put(f"{base_url}/api/users/{target['id']}", json={"role": "superadmin"})
        assert r.status_code == 422, r.text

    def test_invalid_priority_on_project_create_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/projects", json={
            "name": "TEST_p0 bad priority", "priority": "urgent",
        })
        assert r.status_code == 422, r.text

    def test_valid_role_still_works(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/users", json={
            "email": f"test_p0_okrole_{id(self)}@example.com",
            "password": "secret123", "name": "OK Role", "role": "manager",
        })
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "manager"
        admin_client.delete(f"{base_url}/api/users/{r.json()['id']}")

    def test_error_envelope_on_404(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/deals/does-not-exist")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"] == "Deal not found"
        assert body["status_code"] == 404
        assert body["path"] == "/api/deals/does-not-exist"

    def test_error_envelope_on_validation_error(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "x", "stage": "bogus"})
        assert r.status_code == 422
        body = r.json()
        assert isinstance(body["detail"], list)
        assert body["status_code"] == 422
        assert body["path"] == "/api/deals"

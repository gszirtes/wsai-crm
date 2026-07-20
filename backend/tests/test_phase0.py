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

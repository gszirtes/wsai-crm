"""Iteration 3 tests: Utilization reports, Notifications, Email logging on contacts."""
import time
import pytest


# ---------- Utilization report ----------

class TestUtilization:
    def test_admin_can_get_utilization_week(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/reports/utilization?period=week")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["period"] == "week"
        assert "period_start" in data
        assert "totals" in data and set(["total_hours", "billable_hours", "billable_amount"]).issubset(data["totals"].keys())
        assert "users" in data and isinstance(data["users"], list)
        # Each row has expected keys
        if data["users"]:
            row = data["users"][0]
            for k in ("user_id", "name", "role", "total_hours", "billable_hours", "billable_amount", "utilization_pct"):
                assert k in row

    def test_admin_can_get_utilization_month(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/reports/utilization?period=month")
        assert r.status_code == 200
        assert r.json()["period"] == "month"

    def test_manager_can_get_utilization(self, manager_client, base_url):
        r = manager_client.get(f"{base_url}/api/reports/utilization?period=week")
        assert r.status_code == 200

    def test_user_forbidden(self, user_client, base_url):
        r = user_client.get(f"{base_url}/api/reports/utilization?period=week")
        assert r.status_code == 403

    def test_guest_forbidden(self, guest_client, base_url):
        r = guest_client.get(f"{base_url}/api/reports/utilization?period=week")
        assert r.status_code == 403


# ---------- Notifications ----------

class TestNotifications:
    def test_list_notifications_shape(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/notifications")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert "unread" in data and isinstance(data["unread"], int)

    def test_overdue_creates_notification_and_lifecycle(self, admin_client, base_url):
        # 1. Create activity with a past due_date owned by admin
        payload = {
            "type": "task",
            "subject": "TEST_it3 overdue task",
            "description": "past due",
            "due_date": "2026-07-01T09:00:00Z",   # past
            "completed": False,
        }
        cr = admin_client.post(f"{base_url}/api/activities", json=payload)
        assert cr.status_code == 200, cr.text
        activity_id = cr.json()["id"]
        try:
            # 2. GET /api/notifications -> should contain auto_overdue for this activity, unread >= 1
            lr = admin_client.get(f"{base_url}/api/notifications")
            assert lr.status_code == 200
            data = lr.json()
            match = [n for n in data["items"] if n["type"] == "auto_overdue" and (activity_id in (n.get("body") or "") or n.get("body") == payload["subject"])]
            # Notifications use subject as body, so match by subject/body
            match = [n for n in data["items"] if n["type"] == "auto_overdue" and n.get("body") == payload["subject"]]
            assert match, f"No auto_overdue notification found. items={data['items']}"
            n = match[0]
            assert n["read"] is False
            unread_before = data["unread"]
            notif_id = n["id"]

            # 3. POST /api/notifications/{id}/read -> unread drops by 1
            mr = admin_client.post(f"{base_url}/api/notifications/{notif_id}/read")
            assert mr.status_code == 200
            lr2 = admin_client.get(f"{base_url}/api/notifications")
            assert lr2.status_code == 200
            assert lr2.json()["unread"] == max(0, unread_before - 1)
            # The item should now be read=True
            same = [x for x in lr2.json()["items"] if x["id"] == notif_id]
            assert same and same[0]["read"] is True

            # 4. POST /api/notifications/read-all -> unread == 0
            mar = admin_client.post(f"{base_url}/api/notifications/read-all")
            assert mar.status_code == 200
            lr3 = admin_client.get(f"{base_url}/api/notifications")
            assert lr3.json()["unread"] == 0

        finally:
            # 5. Delete underlying activity -> auto notification disappears on next GET
            dr = admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            assert dr.status_code == 200
            lr4 = admin_client.get(f"{base_url}/api/notifications")
            gone = [n for n in lr4.json()["items"] if n.get("body") == payload["subject"] and n["type"] == "auto_overdue"]
            assert not gone, f"Notification still present after activity deletion: {gone}"

    def test_users_see_only_their_own_notifications(self, admin_client, user_client, base_url):
        # Admin creates overdue task owned by admin
        payload = {"type": "task", "subject": "TEST_it3 admin-only overdue",
                   "due_date": "2026-07-02T09:00:00Z", "completed": False}
        cr = admin_client.post(f"{base_url}/api/activities", json=payload)
        assert cr.status_code == 200
        activity_id = cr.json()["id"]
        try:
            # admin sees it
            aitems = admin_client.get(f"{base_url}/api/notifications").json()["items"]
            assert any(n.get("body") == payload["subject"] for n in aitems)
            # user does NOT see it
            uitems = user_client.get(f"{base_url}/api/notifications").json()["items"]
            assert not any(n.get("body") == payload["subject"] for n in uitems)
        finally:
            admin_client.delete(f"{base_url}/api/activities/{activity_id}")


# ---------- Email logging on contacts ----------

class TestEmailLogging:
    def _get_or_create_contact(self, client, base_url):
        # Try to reuse an existing contact
        r = client.get(f"{base_url}/api/contacts")
        assert r.status_code == 200
        contacts = r.json()
        if contacts:
            return contacts[0]["id"], False
        # Otherwise create one
        r = client.post(f"{base_url}/api/contacts", json={
            "first_name": "TEST_it3", "last_name": "Email", "email": "test_it3@example.com",
            "status": "lead",
        })
        assert r.status_code == 200
        return r.json()["id"], True

    def test_admin_can_log_email_activity_shows_in_detail(self, admin_client, base_url):
        contact_id, created = self._get_or_create_contact(admin_client, base_url)
        payload = {
            "type": "email",
            "subject": "[Sent] TEST_it3 hello there",
            "description": "Body of the email logged by test",
            "contact_id": contact_id,
            "completed": True,
        }
        cr = admin_client.post(f"{base_url}/api/activities", json=payload)
        assert cr.status_code == 200, cr.text
        activity_id = cr.json()["id"]
        try:
            # Verify appears in contact detail activities
            dr = admin_client.get(f"{base_url}/api/contacts/{contact_id}/detail")
            assert dr.status_code == 200
            data = dr.json()
            assert "activities" in data
            match = [a for a in data["activities"] if a["id"] == activity_id]
            assert match, "Logged email not found on contact detail activities"
            assert match[0]["type"] == "email"
            assert match[0]["subject"] == payload["subject"]
        finally:
            admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            if created:
                admin_client.delete(f"{base_url}/api/contacts/{contact_id}")

    def test_guest_cannot_log_email(self, admin_client, guest_client, base_url):
        contact_id, created = self._get_or_create_contact(admin_client, base_url)
        try:
            r = guest_client.post(f"{base_url}/api/activities", json={
                "type": "email",
                "subject": "[Sent] guest attempt",
                "description": "should be blocked",
                "contact_id": contact_id,
                "completed": True,
            })
            assert r.status_code == 403
        finally:
            if created:
                admin_client.delete(f"{base_url}/api/contacts/{contact_id}")


# ---------- Regression: 4 role logins still work ----------

class TestRegressionLogins:
    def test_admin_me(self, admin_client, base_url):
        r = admin_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_manager_me(self, manager_client, base_url):
        r = manager_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "manager"

    def test_user_me(self, user_client, base_url):
        r = user_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "user"

    def test_guest_me(self, guest_client, base_url):
        r = guest_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "guest"

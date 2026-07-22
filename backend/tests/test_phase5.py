"""Phase 5 tests: daily housekeeping job, follow-up + referral loop, is_stale flag.

Terv: INTEGRATION_PLAN.md "Fazis 5 - Utemezo + utokoveted + kihuloben".

The scheduled job only fires at 02:00; every test here drives it via the
admin manual-trigger endpoint (POST /api/settings/housekeeping/run), which
runs the exact same run_daily_housekeeping() function.
"""
import pytest


def _run_housekeeping(admin_client, base_url):
    r = admin_client.post(f"{base_url}/api/settings/housekeeping/run")
    assert r.status_code == 200, r.text
    return r.json()


class TestHousekeepingEndpoint:
    def test_non_admin_forbidden(self, user_client, base_url):
        assert user_client.post(f"{base_url}/api/settings/housekeeping/run").status_code == 403

    def test_admin_runs_and_returns_summary(self, admin_client, base_url):
        body = _run_housekeeping(admin_client, base_url)
        assert body["ran"] is True
        for key in ("follow_up_tasks_created", "deals_stale_flag_changed", "users_notifications_synced"):
            assert key in body
        # admin/manager/user/guest are always active in the seeded DB
        assert body["users_notifications_synced"] >= 4


class TestFollowUpTaskCreation:
    def _completed_project(self, admin_client, base_url, name, follow_up_days=0):
        p = admin_client.post(f"{base_url}/api/projects", json={"name": name}).json()
        r = admin_client.put(f"{base_url}/api/projects/{p['id']}", json={
            "name": name, "status": "completed", "follow_up_days": follow_up_days,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_completed_project_past_due_gets_follow_up_task(self, admin_client, base_url):
        p = self._completed_project(admin_client, base_url, "TEST_p5 followup due", follow_up_days=0)
        try:
            _run_housekeeping(admin_client, base_url)
            detail = admin_client.get(f"{base_url}/api/projects/{p['id']}/detail").json()
            assert detail["pending_follow_up"] is not None
            assert detail["pending_follow_up"]["project_id"] == p["id"]
            assert detail["pending_follow_up"]["completed"] is False
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_not_yet_due_project_gets_no_follow_up_task(self, admin_client, base_url):
        p = self._completed_project(admin_client, base_url, "TEST_p5 followup not due", follow_up_days=60)
        try:
            _run_housekeeping(admin_client, base_url)
            detail = admin_client.get(f"{base_url}/api/projects/{p['id']}/detail").json()
            assert detail["pending_follow_up"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_non_completed_project_gets_no_follow_up_task(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p5 active project"}).json()
        try:
            _run_housekeeping(admin_client, base_url)
            detail = admin_client.get(f"{base_url}/api/projects/{p['id']}/detail").json()
            assert detail["pending_follow_up"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_follow_up_task_creation_is_idempotent(self, admin_client, base_url):
        p = self._completed_project(admin_client, base_url, "TEST_p5 followup idempotent", follow_up_days=0)
        try:
            _run_housekeeping(admin_client, base_url)
            first = admin_client.get(f"{base_url}/api/projects/{p['id']}/detail").json()["pending_follow_up"]
            _run_housekeeping(admin_client, base_url)
            second = admin_client.get(f"{base_url}/api/projects/{p['id']}/detail").json()["pending_follow_up"]
            assert first["id"] == second["id"]
            activities = admin_client.get(f"{base_url}/api/activities", params={"project_id": p["id"]}).json()
            assert len(activities) == 1
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_reopening_completed_project_clears_closed_at(self, admin_client, base_url):
        p = self._completed_project(admin_client, base_url, "TEST_p5 reopen clears closed_at")
        try:
            assert admin_client.get(f"{base_url}/api/projects/{p['id']}").json()["closed_at"] is not None
            r = admin_client.put(f"{base_url}/api/projects/{p['id']}", json={
                "name": "TEST_p5 reopen clears closed_at", "status": "active",
            })
            assert r.status_code == 200, r.text
            assert r.json()["closed_at"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")


class TestStaleFlag:
    def _with_stale_days(self, admin_client, base_url, value):
        original = admin_client.get(f"{base_url}/api/settings/thresholds").json()
        admin_client.put(f"{base_url}/api/settings/thresholds", json={**original, "stale_days": value})
        return original

    def test_stale_flag_set_when_ball_in_court_us_past_threshold(self, admin_client, base_url):
        original = self._with_stale_days(admin_client, base_url, 0)
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p5 stale deal"}).json()
        activity_id = None
        try:
            ar = admin_client.post(f"{base_url}/api/activities", json={
                "type": "email", "direction": "inbound", "subject": "TEST_p5 stale inbound", "deal_id": d["id"],
            })
            activity_id = ar.json()["id"]
            _run_housekeeping(admin_client, base_url)
            assert admin_client.get(f"{base_url}/api/deals/{d['id']}").json()["is_stale"] is True
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            if activity_id:
                admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_stale_flag_cleared_when_ball_in_court_not_us(self, admin_client, base_url):
        original = self._with_stale_days(admin_client, base_url, 0)
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p5 stale then cleared"}).json()
        activity_id = None
        try:
            ar = admin_client.post(f"{base_url}/api/activities", json={
                "type": "email", "direction": "inbound", "subject": "TEST_p5 stale inbound 2", "deal_id": d["id"],
            })
            activity_id = ar.json()["id"]
            _run_housekeeping(admin_client, base_url)
            assert admin_client.get(f"{base_url}/api/deals/{d['id']}").json()["is_stale"] is True

            admin_client.patch(f"{base_url}/api/deals/{d['id']}/ball-in-court", json={"ball_in_court": "them"})
            _run_housekeeping(admin_client, base_url)
            assert admin_client.get(f"{base_url}/api/deals/{d['id']}").json()["is_stale"] is False
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            if activity_id:
                admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_stale_flag_not_set_before_threshold(self, admin_client, base_url):
        original = self._with_stale_days(admin_client, base_url, 999)
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p5 not stale yet"}).json()
        activity_id = None
        try:
            ar = admin_client.post(f"{base_url}/api/activities", json={
                "type": "email", "direction": "inbound", "subject": "TEST_p5 not stale inbound", "deal_id": d["id"],
            })
            activity_id = ar.json()["id"]
            _run_housekeeping(admin_client, base_url)
            assert admin_client.get(f"{base_url}/api/deals/{d['id']}").json()["is_stale"] is False
        finally:
            admin_client.put(f"{base_url}/api/settings/thresholds", json=original)
            if activity_id:
                admin_client.delete(f"{base_url}/api/activities/{activity_id}")
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")


class TestFollowUpCompletion:
    def _project_with_pending_follow_up(self, admin_client, base_url, name):
        p = admin_client.post(f"{base_url}/api/projects", json={"name": name}).json()
        admin_client.put(f"{base_url}/api/projects/{p['id']}", json={
            "name": name, "status": "completed", "follow_up_days": 0,
        })
        _run_housekeeping(admin_client, base_url)
        return p["id"]

    def test_complete_follow_up_records_satisfaction(self, admin_client, base_url):
        project_id = self._project_with_pending_follow_up(admin_client, base_url, "TEST_p5 satisfaction")
        try:
            r = admin_client.post(f"{base_url}/api/projects/{project_id}/follow-up",
                                  json={"satisfaction_score": 4})
            assert r.status_code == 200, r.text
            assert r.json()["project"]["satisfaction_score"] == 4
            assert r.json()["referral_deal_id"] is None
            detail = admin_client.get(f"{base_url}/api/projects/{project_id}/detail").json()
            assert detail["pending_follow_up"] is None
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_complete_follow_up_with_referral_creates_deal_and_tags_contact(self, admin_client, base_url):
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p5 referrer"}).json()
        project_id = self._project_with_pending_follow_up(admin_client, base_url, "TEST_p5 referral project")
        deal_id = None
        try:
            r = admin_client.post(f"{base_url}/api/projects/{project_id}/follow-up", json={
                "satisfaction_score": 5, "referred_contact_id": contact["id"],
            })
            assert r.status_code == 200, r.text
            deal_id = r.json()["referral_deal_id"]
            assert deal_id is not None
            deal = admin_client.get(f"{base_url}/api/deals/{deal_id}").json()
            assert deal["referred_by_contact_id"] == contact["id"]
            assert deal["owner_id"] is None
            assert deal["lead_type"] == "single"
            updated_contact = admin_client.get(f"{base_url}/api/contacts/{contact['id']}").json()
            assert "referrer" in updated_contact["tags"]
        finally:
            if deal_id:
                admin_client.delete(f"{base_url}/api/deals/{deal_id}")
            admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")

    def test_complete_follow_up_without_pending_task_400(self, admin_client, base_url):
        p = admin_client.post(f"{base_url}/api/projects", json={"name": "TEST_p5 no pending"}).json()
        try:
            r = admin_client.post(f"{base_url}/api/projects/{p['id']}/follow-up", json={"satisfaction_score": 3})
            assert r.status_code == 400
        finally:
            admin_client.delete(f"{base_url}/api/projects/{p['id']}")

    def test_referral_requires_manage_deals(self, admin_client, user_client, base_url):
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p5 blocked referrer"}).json()
        project_id = self._project_with_pending_follow_up(admin_client, base_url, "TEST_p5 blocked referral")
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            revoked = {**original, "user": {**original["user"], "manage_deals": False}}
            admin_client.put(f"{base_url}/api/settings/capabilities", json=revoked)
            r = user_client.post(f"{base_url}/api/projects/{project_id}/follow-up",
                                 json={"referred_contact_id": contact["id"]})
            assert r.status_code == 403, r.text
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)
            admin_client.delete(f"{base_url}/api/projects/{project_id}")
            admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")

    def test_follow_up_404_for_private_project_non_member(self, admin_client, user_client, base_url):
        project_id = self._project_with_pending_follow_up(admin_client, base_url, "TEST_p5 private followup")
        try:
            admin_client.patch(f"{base_url}/api/projects/{project_id}/visibility", json={"visibility": "private"})
            r = user_client.post(f"{base_url}/api/projects/{project_id}/follow-up", json={"satisfaction_score": 3})
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

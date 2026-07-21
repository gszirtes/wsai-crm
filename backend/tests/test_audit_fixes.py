"""Regression tests for docs/audits/2026-07-21-phase0-phase1-security-audit.md.

Covers the highest-severity findings: the activities/time-entry visibility
IDOR (SEC-1), the two ServiceAccount FK-crash bugs (BUG-1/BUG-2), the
capability-matrix self-lockout guard (BUG-3), CSV formula-injection
sanitization (SEC-2), and the auth-refresh active check (SEC-5).
"""
import requests


def _user_id_by_email(client, base_url, email):
    r = client.get(f"{base_url}/api/users/directory")
    assert r.status_code == 200, r.text
    match = [u for u in r.json() if u["email"] == email]
    assert match, f"seeded user {email} not found in directory"
    return match[0]["id"]


class TestActivitiesVisibilityIDOR:
    """SEC-1: activities.py had no can_see() gate on the linked deal/project,
    unlike every other Deal/Project-adjacent endpoint."""

    def _make_private_deal(self, admin_client, base_url, title="TEST_audit private deal"):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": title})
        deal_id = r.json()["id"]
        pr = admin_client.patch(f"{base_url}/api/deals/{deal_id}/visibility", json={"visibility": "private"})
        assert pr.status_code == 200, pr.text
        return deal_id

    def test_list_activities_404_for_non_member_private_deal(self, admin_client, user_client, base_url):
        deal_id = self._make_private_deal(admin_client, base_url)
        try:
            r = user_client.get(f"{base_url}/api/activities", params={"deal_id": deal_id})
            assert r.status_code == 404, r.text
            r_admin = admin_client.get(f"{base_url}/api/activities", params={"deal_id": deal_id})
            assert r_admin.status_code == 200, r_admin.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_create_activity_404_for_non_member_private_deal(self, admin_client, user_client, base_url):
        deal_id = self._make_private_deal(admin_client, base_url, title="TEST_audit private deal create")
        try:
            r = user_client.post(f"{base_url}/api/activities", json={
                "type": "task", "subject": "TEST_audit sneaky activity", "deal_id": deal_id,
            })
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_member_can_list_and_create_activities_on_private_deal(self, admin_client, user_client, base_url):
        deal_id = self._make_private_deal(admin_client, base_url, title="TEST_audit member deal")
        try:
            user_id = _user_id_by_email(admin_client, base_url, "user@wespeak.ai")
            admin_client.post(f"{base_url}/api/deals/{deal_id}/members", json={"user_id": user_id})
            assert user_client.get(f"{base_url}/api/activities", params={"deal_id": deal_id}).status_code == 200
            cr = user_client.post(f"{base_url}/api/activities", json={
                "type": "task", "subject": "TEST_audit member activity", "deal_id": deal_id,
            })
            assert cr.status_code == 200, cr.text
            user_client.delete(f"{base_url}/api/activities/{cr.json()['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")

    def test_existing_activity_write_endpoints_404_for_non_member(self, admin_client, user_client, base_url):
        deal_id = self._make_private_deal(admin_client, base_url, title="TEST_audit deal for activity writes")
        try:
            a = admin_client.post(f"{base_url}/api/activities", json={
                "type": "task", "subject": "TEST_audit activity writes", "deal_id": deal_id,
            }).json()
            try:
                assert user_client.patch(f"{base_url}/api/activities/{a['id']}/toggle").status_code == 404
                assert user_client.delete(f"{base_url}/api/activities/{a['id']}").status_code == 404
            finally:
                admin_client.delete(f"{base_url}/api/activities/{a['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")


class TestProjectTimeVisibilityIDOR:
    """SEC-1: projects.py time-entry sub-resource had no can_see() gate,
    unlike every other project endpoint in the same file."""

    def _make_private_project(self, admin_client, base_url, name="TEST_audit private project"):
        r = admin_client.post(f"{base_url}/api/projects", json={"name": name})
        project_id = r.json()["id"]
        pr = admin_client.patch(f"{base_url}/api/projects/{project_id}/visibility", json={"visibility": "private"})
        assert pr.status_code == 200, pr.text
        return project_id

    def test_list_time_404_for_non_member(self, admin_client, user_client, base_url):
        project_id = self._make_private_project(admin_client, base_url)
        try:
            assert user_client.get(f"{base_url}/api/projects/{project_id}/time").status_code == 404
            assert admin_client.get(f"{base_url}/api/projects/{project_id}/time").status_code == 200
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_add_time_404_for_non_member(self, admin_client, user_client, base_url):
        project_id = self._make_private_project(admin_client, base_url, name="TEST_audit private project add")
        try:
            r = user_client.post(f"{base_url}/api/projects/{project_id}/time", json={"hours": 1.5})
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_delete_time_404_for_non_member(self, admin_client, user_client, base_url):
        project_id = self._make_private_project(admin_client, base_url, name="TEST_audit private project delete")
        try:
            entry = admin_client.post(f"{base_url}/api/projects/{project_id}/time", json={"hours": 2}).json()
            r = user_client.delete(f"{base_url}/api/projects/{project_id}/time/{entry['id']}")
            assert r.status_code == 404, r.text
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")

    def test_member_can_use_time_endpoints_on_private_project(self, admin_client, user_client, base_url):
        project_id = self._make_private_project(admin_client, base_url, name="TEST_audit member project")
        try:
            user_id = _user_id_by_email(admin_client, base_url, "user@wespeak.ai")
            admin_client.post(f"{base_url}/api/projects/{project_id}/members", json={"user_id": user_id})
            assert user_client.get(f"{base_url}/api/projects/{project_id}/time").status_code == 200
            cr = user_client.post(f"{base_url}/api/projects/{project_id}/time", json={"hours": 1})
            assert cr.status_code == 200, cr.text
        finally:
            admin_client.delete(f"{base_url}/api/projects/{project_id}")


class TestServiceAccountFKGuards:
    """BUG-1/BUG-2: created_by / added_by were set from the raw principal id
    without an owner_id_for()-style guard, so an admin- or manager-role
    ServiceAccount crashed with a ForeignKeyViolation on these two paths."""

    def test_admin_role_service_account_can_create_another_service_account(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/service-accounts",
                               json={"name": "TEST_audit sa admin", "role": "admin"})
        sa_id, api_key = cr.json()["id"], cr.json()["api_key"]
        child_id = None
        try:
            r = requests.post(f"{base_url}/api/service-accounts",
                              json={"name": "TEST_audit sa child", "role": "user"},
                              headers={"X-API-Key": api_key}, timeout=20)
            assert r.status_code == 200, r.text
            child_id = r.json()["id"]
        finally:
            if child_id:
                admin_client.delete(f"{base_url}/api/service-accounts/{child_id}")
            admin_client.delete(f"{base_url}/api/service-accounts/{sa_id}")

    def test_manager_role_service_account_can_invite_deal_member(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/service-accounts",
                               json={"name": "TEST_audit sa manager", "role": "manager"})
        sa_id, api_key = cr.json()["id"], cr.json()["api_key"]
        deal_id = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_audit sa invite deal"}).json()["id"]
        try:
            user_id = _user_id_by_email(admin_client, base_url, "user@wespeak.ai")
            r = requests.post(f"{base_url}/api/deals/{deal_id}/members", json={"user_id": user_id},
                              headers={"X-API-Key": api_key}, timeout=20)
            assert r.status_code == 200, r.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{deal_id}")
            admin_client.delete(f"{base_url}/api/service-accounts/{sa_id}")


class TestCapabilityMatrixFloor:
    """BUG-3: PUT /settings/capabilities silently accepted admin/manager
    capabilities set to False, which (since writes are capability-gated, not
    role-gated) could lock every admin out. set_capability_matrix() now
    forces those two rows to all-True regardless of the payload."""

    def test_admin_manage_deals_cannot_be_turned_off(self, admin_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            tampered = {**original, "admin": {**original["admin"], "manage_deals": False}}
            r = admin_client.put(f"{base_url}/api/settings/capabilities", json=tampered)
            assert r.status_code == 200, r.text
            assert r.json()["admin"]["manage_deals"] is True
            persisted = admin_client.get(f"{base_url}/api/settings/capabilities").json()
            assert persisted["admin"]["manage_deals"] is True
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)

    def test_manager_view_financials_cannot_be_turned_off(self, admin_client, base_url):
        original = admin_client.get(f"{base_url}/api/settings/capabilities").json()
        try:
            tampered = {**original, "manager": {**original["manager"], "view_financials": False}}
            r = admin_client.put(f"{base_url}/api/settings/capabilities", json=tampered)
            assert r.status_code == 200, r.text
            assert r.json()["manager"]["view_financials"] is True
        finally:
            admin_client.put(f"{base_url}/api/settings/capabilities", json=original)


class TestCSVFormulaInjection:
    """SEC-2: a company/contact name starting with =/+/-/@ used to be written
    to CSV cells verbatim, which Excel/Sheets would interpret as a formula."""

    def test_company_name_with_formula_prefix_is_neutralized_in_export(self, admin_client, base_url):
        name = "=cmd|'/c calc'!A1"
        cr = admin_client.post(f"{base_url}/api/companies", json={"name": name})
        company_id = cr.json()["id"]
        try:
            csv_text = admin_client.get(f"{base_url}/api/export/companies.csv").text
            # name is the CSV's first column, so it's row-leading (preceded
            # by \r\n, not a comma) -- the raw value is still a substring of
            # the sanitized (quote-prefixed) cell, so assert on the exact
            # cell boundary instead of plain substring containment.
            assert f"\r\n{name}," not in csv_text, "unescaped formula-leading cell must not appear"
            assert f"\r\n'{name}," in csv_text, "expected the quote-prefixed, spreadsheet-safe form"
        finally:
            admin_client.delete(f"{base_url}/api/companies/{company_id}")

    def test_contact_last_name_with_at_sign_is_neutralized_in_export(self, admin_client, base_url):
        cr = admin_client.post(f"{base_url}/api/contacts", json={
            "first_name": "TEST_audit", "last_name": "@SUM(1+1)",
        })
        contact_id = cr.json()["id"]
        try:
            csv_text = admin_client.get(f"{base_url}/api/export/contacts.csv").text
            assert ",@SUM(1+1)," not in csv_text
            assert ",'@SUM(1+1)," in csv_text
        finally:
            admin_client.delete(f"{base_url}/api/contacts/{contact_id}")


class TestAuthRefreshActiveCheck:
    """SEC-5: /api/auth/refresh only validated the JWT signature/type, never
    whether the user had since been deactivated. Admin creates a throwaway
    user (self-registration is disabled by default, so this is the only way
    to get a fresh account in this suite), logs in as them to capture a
    refresh cookie, then deactivates them and confirms refresh is rejected."""

    def test_deactivated_user_refresh_token_rejected(self, admin_client, base_url):
        email = "test_audit_refresh_user@wespeak.ai"
        cr = admin_client.post(f"{base_url}/api/users", json={
            "email": email, "password": "TestAudit123!", "name": "TEST_audit refresh user", "role": "user",
        })
        assert cr.status_code == 200, cr.text
        user_id = cr.json()["id"]
        try:
            s = requests.Session()
            s.headers.update({"Content-Type": "application/json"})
            lr = s.post(f"{base_url}/api/auth/login", json={"email": email, "password": "TestAudit123!"})
            assert lr.status_code == 200, lr.text

            dr = admin_client.put(f"{base_url}/api/users/{user_id}", json={"active": False})
            assert dr.status_code == 200, dr.text

            rr = s.post(f"{base_url}/api/auth/refresh")
            assert rr.status_code == 403, rr.text
        finally:
            admin_client.delete(f"{base_url}/api/users/{user_id}")

    def test_active_user_refresh_still_works(self, admin_client, base_url):
        email = "test_audit_refresh_active@wespeak.ai"
        cr = admin_client.post(f"{base_url}/api/users", json={
            "email": email, "password": "TestAudit123!", "name": "TEST_audit refresh active", "role": "user",
        })
        assert cr.status_code == 200, cr.text
        user_id = cr.json()["id"]
        try:
            s = requests.Session()
            s.headers.update({"Content-Type": "application/json"})
            lr = s.post(f"{base_url}/api/auth/login", json={"email": email, "password": "TestAudit123!"})
            assert lr.status_code == 200, lr.text
            rr = s.post(f"{base_url}/api/auth/refresh")
            assert rr.status_code == 200, rr.text
        finally:
            admin_client.delete(f"{base_url}/api/users/{user_id}")

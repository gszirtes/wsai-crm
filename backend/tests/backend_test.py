"""Comprehensive backend test suite for wespeak.ai CRM."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://785d7db7-5035-4ba8-9f51-6bb14185c330.preview.emergentagent.com").rstrip("/")


# ---------- Health ----------
class TestHealth:
    def test_health_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "wespeak-crm"


# ---------- Auth ----------
class TestAuth:
    @pytest.mark.parametrize("email,password,expected_role", [
        ("admin@wespeak.ai", "admin123", "admin"),
        ("manager@wespeak.ai", "manager123", "manager"),
        ("user@wespeak.ai", "user123", "user"),
        ("guest@wespeak.ai", "guest123", "guest"),
    ])
    def test_login_seeded_accounts(self, email, password, expected_role):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == expected_role
        # httpOnly cookie must be set
        assert "access_token" in s.cookies
        assert "refresh_token" in s.cookies
        # /me works with cookie
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=20)
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_login_invalid_password(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@wespeak.ai", "password": "wrong"}, timeout=20)
        assert r.status_code == 401

    def test_register_new_user(self):
        email = f"test_{uuid.uuid4().hex[:8]}@wespeak.ai"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register",
                   json={"email": email, "password": "secret123", "name": "Test Register"}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "user"
        # cleanup - login as admin and delete
        a = requests.Session()
        a.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@wespeak.ai", "password": "admin123"}, timeout=20)
        a.delete(f"{BASE_URL}/api/users/{data['id']}", timeout=20)


# ---------- Contacts ----------
class TestContacts:
    def test_contacts_full_crud(self, admin_client):
        # create
        payload = {"first_name": "TEST_John", "last_name": "Doe", "email": "TEST_john@example.com",
                   "title": "Engineer", "status": "lead"}
        r = admin_client.post(f"{BASE_URL}/api/contacts", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["first_name"] == "TEST_John"
        assert "id" in c
        cid = c["id"]

        # list
        r = admin_client.get(f"{BASE_URL}/api/contacts", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == cid for x in r.json())

        # search
        r = admin_client.get(f"{BASE_URL}/api/contacts?search=TEST_John", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == cid for x in r.json())

        # status filter
        r = admin_client.get(f"{BASE_URL}/api/contacts?status=lead", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == cid for x in r.json())

        # update
        payload_upd = {**payload, "first_name": "TEST_John2", "status": "customer"}
        r = admin_client.put(f"{BASE_URL}/api/contacts/{cid}", json=payload_upd, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["first_name"] == "TEST_John2"

        # get by id verifies persistence
        r = admin_client.get(f"{BASE_URL}/api/contacts/{cid}", timeout=20)
        assert r.status_code == 200
        assert r.json()["status"] == "customer"

        # delete
        r = admin_client.delete(f"{BASE_URL}/api/contacts/{cid}", timeout=20)
        assert r.status_code == 200
        r = admin_client.get(f"{BASE_URL}/api/contacts/{cid}", timeout=20)
        assert r.status_code == 404


# ---------- Companies ----------
class TestCompanies:
    def test_companies_full_crud(self, admin_client):
        payload = {"name": "TEST_Acme Corp", "industry": "SaaS", "website": "test.com"}
        r = admin_client.post(f"{BASE_URL}/api/companies", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        r = admin_client.get(f"{BASE_URL}/api/companies?search=TEST_Acme", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == cid for x in r.json())

        r = admin_client.put(f"{BASE_URL}/api/companies/{cid}",
                             json={**payload, "industry": "AI"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["industry"] == "AI"

        r = admin_client.delete(f"{BASE_URL}/api/companies/{cid}", timeout=20)
        assert r.status_code == 200


# ---------- Deals ----------
class TestDeals:
    def test_deals_full_crud_and_stage(self, admin_client):
        payload = {"title": "TEST_Big Deal", "value": 1000, "currency": "EUR",
                   "stage": "lead", "probability": 10}
        r = admin_client.post(f"{BASE_URL}/api/deals", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        did = r.json()["id"]
        assert r.json()["stage"] == "lead"

        # list
        r = admin_client.get(f"{BASE_URL}/api/deals", timeout=20)
        assert r.status_code == 200

        # PATCH stage
        r = admin_client.patch(f"{BASE_URL}/api/deals/{did}/stage",
                               json={"stage": "proposal"}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["stage"] == "proposal"
        assert data["probability"] == 55  # per STAGE_PROBABILITY map

        # PATCH stage to won
        r = admin_client.patch(f"{BASE_URL}/api/deals/{did}/stage",
                               json={"stage": "won"}, timeout=20)
        assert r.json()["probability"] == 100

        # delete
        r = admin_client.delete(f"{BASE_URL}/api/deals/{did}", timeout=20)
        assert r.status_code == 200


# ---------- Projects ----------
class TestProjects:
    def test_projects_full_crud(self, admin_client):
        payload = {"name": "TEST_Project X", "description": "Testing", "status": "planning",
                   "priority": "high", "budget": 5000}
        r = admin_client.post(f"{BASE_URL}/api/projects", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]

        r = admin_client.get(f"{BASE_URL}/api/projects?status=planning", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == pid for x in r.json())

        r = admin_client.put(f"{BASE_URL}/api/projects/{pid}",
                             json={**payload, "status": "active"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        r = admin_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=20)
        assert r.status_code == 200


# ---------- Activities ----------
class TestActivities:
    def test_activities_full_crud_and_toggle(self, admin_client):
        payload = {"type": "task", "subject": "TEST_Do something", "completed": False}
        r = admin_client.post(f"{BASE_URL}/api/activities", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        aid = r.json()["id"]

        r = admin_client.get(f"{BASE_URL}/api/activities?completed=false", timeout=20)
        assert r.status_code == 200
        assert any(x["id"] == aid for x in r.json())

        r = admin_client.patch(f"{BASE_URL}/api/activities/{aid}/toggle", timeout=20)
        assert r.status_code == 200
        assert r.json()["completed"] is True

        r = admin_client.get(f"{BASE_URL}/api/activities?completed=true", timeout=20)
        assert any(x["id"] == aid for x in r.json())

        r = admin_client.delete(f"{BASE_URL}/api/activities/{aid}", timeout=20)
        assert r.status_code == 200


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_stats(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/dashboard/stats", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["total_contacts", "total_companies", "active_projects", "open_deals",
                  "pipeline_value", "won_value", "open_tasks",
                  "deals_by_stage", "contacts_by_status", "projects_by_status"]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["deals_by_stage"], list)
        assert isinstance(d["contacts_by_status"], list)


# ---------- RBAC ----------
class TestRBAC:
    def test_guest_read_allowed(self, guest_client):
        for path in ["/api/contacts", "/api/companies", "/api/deals",
                     "/api/projects", "/api/activities", "/api/dashboard/stats"]:
            r = guest_client.get(f"{BASE_URL}{path}", timeout=20)
            assert r.status_code == 200, f"GET {path} failed: {r.status_code}"

    def test_guest_write_blocked(self, guest_client):
        payloads = {
            "/api/contacts": {"first_name": "X"},
            "/api/companies": {"name": "X"},
            "/api/deals": {"title": "X"},
            "/api/projects": {"name": "X"},
            "/api/activities": {"subject": "X"},
        }
        for path, body in payloads.items():
            r = guest_client.post(f"{BASE_URL}{path}", json=body, timeout=20)
            assert r.status_code == 403, f"POST {path} expected 403 got {r.status_code}"

    def test_admin_only_users_endpoint(self, user_client, admin_client):
        # non-admin cannot POST /api/users
        r = user_client.post(f"{BASE_URL}/api/users",
                             json={"email": "x@x.com", "password": "abcdef", "name": "X"}, timeout=20)
        assert r.status_code == 403

        # non-admin cannot GET/PUT /api/settings
        r = user_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert r.status_code == 403
        r = user_client.put(f"{BASE_URL}/api/settings",
                            json={"openrouter_model": "x"}, timeout=20)
        assert r.status_code == 403

        # admin CAN
        r = admin_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert r.status_code == 200
        assert "openrouter_configured" in r.json()


# ---------- Admin User Management ----------
class TestAdminUserMgmt:
    def test_admin_create_update_and_self_delete_block(self, admin_client):
        email = f"TEST_mgmt_{uuid.uuid4().hex[:6]}@wespeak.ai"
        # create user with 'manager' role
        r = admin_client.post(f"{BASE_URL}/api/users",
                              json={"email": email, "password": "abcdef", "name": "TEST User",
                                    "role": "manager"}, timeout=20)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        assert r.json()["role"] == "manager"

        # update role to user
        r = admin_client.put(f"{BASE_URL}/api/users/{uid}", json={"role": "user"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["role"] == "user"

        # cannot delete self
        me = admin_client.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
        r = admin_client.delete(f"{BASE_URL}/api/users/{me['id']}", timeout=20)
        assert r.status_code == 400

        # cleanup created user
        r = admin_client.delete(f"{BASE_URL}/api/users/{uid}", timeout=20)
        assert r.status_code == 200


# ---------- AI (expected 400 no key) ----------
class TestAI:
    def test_ai_command_no_key(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/command",
                              json={"command": "hello"}, timeout=20)
        assert r.status_code == 400
        assert "OpenRouter" in r.json()["detail"]

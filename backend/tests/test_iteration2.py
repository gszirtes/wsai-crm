"""Iteration 2 backend tests: time tracking, health, detail endpoints, CSV import/export, RBAC."""
import os
import io
import csv
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


# ---------- Project time tracking + health ----------
class TestProjectTimeTracking:
    def _create_project(self, client, estimated_hours=10, hourly_rate=100):
        payload = {"name": f"TEST_TimeProj_{uuid.uuid4().hex[:6]}",
                   "description": "For time tracking",
                   "status": "active", "priority": "high",
                   "budget": 5000, "estimated_hours": estimated_hours,
                   "hourly_rate": hourly_rate}
        r = client.post(f"{BASE_URL}/api/projects", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Persisted new fields
        assert data["estimated_hours"] == estimated_hours
        assert data["hourly_rate"] == hourly_rate
        # health present on list output
        return data

    def test_project_lists_include_health_and_logged_hours(self, admin_client):
        p = self._create_project(admin_client)
        try:
            r = admin_client.get(f"{BASE_URL}/api/projects", timeout=20)
            assert r.status_code == 200
            found = next((x for x in r.json() if x["id"] == p["id"]), None)
            assert found is not None
            assert "health" in found and found["health"] in [
                "on_track", "at_risk", "over_budget", "completed", "cancelled"]
            assert "logged_hours" in found
            assert found["logged_hours"] == 0
        finally:
            admin_client.delete(f"{BASE_URL}/api/projects/{p['id']}", timeout=20)

    def test_log_time_and_detail_and_delete(self, admin_client):
        p = self._create_project(admin_client, estimated_hours=10, hourly_rate=120)
        pid = p["id"]
        try:
            # log 4 billable hours
            r = admin_client.post(f"{BASE_URL}/api/projects/{pid}/time",
                                  json={"hours": 4, "description": "TEST_work",
                                        "billable": True}, timeout=20)
            assert r.status_code == 200, r.text
            entry = r.json()
            assert entry["hours"] == 4
            assert entry["billable"] is True
            eid = entry["id"]

            # log 2 non-billable hours
            r = admin_client.post(f"{BASE_URL}/api/projects/{pid}/time",
                                  json={"hours": 2, "description": "TEST_notes",
                                        "billable": False}, timeout=20)
            assert r.status_code == 200

            # get detail
            r = admin_client.get(f"{BASE_URL}/api/projects/{pid}/detail", timeout=20)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["logged_hours"] == 6
            assert d["billable_hours"] == 4
            assert d["billable_amount"] == 4 * 120
            assert d["health"] == "on_track"
            assert len(d["time_entries"]) == 2
            assert "activities" in d

            # delete one entry
            r = admin_client.delete(f"{BASE_URL}/api/projects/{pid}/time/{eid}", timeout=20)
            assert r.status_code == 200

            # Verify subtract
            r = admin_client.get(f"{BASE_URL}/api/projects/{pid}/detail", timeout=20)
            assert r.json()["logged_hours"] == 2
        finally:
            admin_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=20)

    def test_health_over_budget(self, admin_client):
        p = self._create_project(admin_client, estimated_hours=2, hourly_rate=50)
        pid = p["id"]
        try:
            admin_client.post(f"{BASE_URL}/api/projects/{pid}/time",
                              json={"hours": 5, "billable": True}, timeout=20)
            r = admin_client.get(f"{BASE_URL}/api/projects/{pid}/detail", timeout=20)
            assert r.status_code == 200
            assert r.json()["health"] == "over_budget"
        finally:
            admin_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=20)

    def test_health_completed(self, admin_client):
        p = self._create_project(admin_client)
        pid = p["id"]
        try:
            payload = {"name": p["name"], "description": "x", "status": "completed",
                       "priority": "high", "budget": 5000,
                       "estimated_hours": 10, "hourly_rate": 100}
            r = admin_client.put(f"{BASE_URL}/api/projects/{pid}", json=payload, timeout=20)
            assert r.status_code == 200
            assert r.json()["health"] == "completed"
        finally:
            admin_client.delete(f"{BASE_URL}/api/projects/{pid}", timeout=20)


# ---------- Detail endpoints ----------
class TestDetailEndpoints:
    def test_contact_detail(self, admin_client):
        # find a seeded contact
        r = admin_client.get(f"{BASE_URL}/api/contacts", timeout=20)
        assert r.status_code == 200
        contacts = r.json()
        assert len(contacts) > 0
        cid = contacts[0]["id"]
        r = admin_client.get(f"{BASE_URL}/api/contacts/{cid}/detail", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "contact" in d
        assert d["contact"]["id"] == cid
        assert "deals" in d and isinstance(d["deals"], list)
        assert "activities" in d and isinstance(d["activities"], list)

    def test_company_detail(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/companies", timeout=20)
        assert r.status_code == 200
        cid = r.json()[0]["id"]
        r = admin_client.get(f"{BASE_URL}/api/companies/{cid}/detail", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["company"]["id"] == cid
        for k in ["contacts", "deals", "projects"]:
            assert k in d and isinstance(d[k], list)

    def test_deal_detail(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/deals", timeout=20)
        assert r.status_code == 200
        did = r.json()[0]["id"]
        r = admin_client.get(f"{BASE_URL}/api/deals/{did}/detail", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["deal"]["id"] == did
        assert "company_name" in d
        assert "contact_name" in d
        assert "activities" in d

    def test_detail_404(self, admin_client):
        for path in ["/api/contacts/nonexistent/detail",
                     "/api/companies/nonexistent/detail",
                     "/api/deals/nonexistent/detail",
                     "/api/projects/nonexistent/detail"]:
            r = admin_client.get(f"{BASE_URL}{path}", timeout=20)
            assert r.status_code == 404


# ---------- CSV export ----------
class TestCSVExport:
    @pytest.mark.parametrize("endpoint,expected_headers", [
        ("/api/export/contacts.csv",
         ["first_name", "last_name", "email", "phone", "title", "status", "company"]),
        ("/api/export/companies.csv",
         ["name", "industry", "website", "email", "phone", "size", "address"]),
        ("/api/export/deals.csv",
         ["title", "value", "currency", "stage", "probability"]),
        ("/api/export/projects.csv",
         ["name", "status", "priority", "budget", "estimated_hours"]),
    ])
    def test_export_endpoints(self, admin_client, endpoint, expected_headers):
        r = admin_client.get(f"{BASE_URL}{endpoint}", timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        text = r.text
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        assert header == expected_headers


# ---------- CSV import ----------
class TestCSVImport:
    def test_import_contacts_creates_contacts_and_companies(self, admin_client):
        unique = uuid.uuid4().hex[:6]
        company_name = f"TEST_ImportCo_{unique}"
        csv_content = (
            "first_name,last_name,email,company\n"
            f"TEST_Alice_{unique},Test,test_alice_{unique}@example.com,{company_name}\n"
            f"TEST_Bob_{unique},Test,test_bob_{unique}@example.com,{company_name}\n"
            ",Missing,test_missing_{}@example.com,{}\n".format(unique, company_name)
        )
        files = {"file": (f"import_{unique}.csv", csv_content.encode("utf-8"), "text/csv")}
        # cannot use json headers when uploading multipart. Use a fresh session copy.
        s = requests.Session()
        # login as admin
        s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@wespeak.ai", "password": "admin123"}, timeout=20)
        r = s.post(f"{BASE_URL}/api/import/contacts", files=files, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] == 2
        assert len(d["errors"]) == 1  # row 4 missing first_name

        # verify contacts + company created
        r = s.get(f"{BASE_URL}/api/contacts?search=TEST_Alice_{unique}", timeout=20)
        assert r.status_code == 200
        assert len(r.json()) == 1
        alice = r.json()[0]
        assert alice["company_name"] == company_name

        r = s.get(f"{BASE_URL}/api/companies?search={company_name}", timeout=20)
        assert r.status_code == 200
        matched = [c for c in r.json() if c["name"] == company_name]
        assert len(matched) == 1
        cleanup_company_id = matched[0]["id"]

        # cleanup created contacts
        r = s.get(f"{BASE_URL}/api/contacts?search=TEST_", timeout=20)
        for c in r.json():
            if unique in (c.get("first_name") or ""):
                s.delete(f"{BASE_URL}/api/contacts/{c['id']}", timeout=20)
        s.delete(f"{BASE_URL}/api/companies/{cleanup_company_id}", timeout=20)

    def test_import_rejects_non_csv(self, admin_client):
        s = requests.Session()
        s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@wespeak.ai", "password": "admin123"}, timeout=20)
        files = {"file": ("bad.txt", b"first_name\nAlice\n", "text/plain")}
        r = s.post(f"{BASE_URL}/api/import/contacts", files=files, timeout=20)
        assert r.status_code == 400


# ---------- RBAC on new endpoints ----------
class TestNewEndpointRBAC:
    def _get_seed_project_id(self, client):
        r = client.get(f"{BASE_URL}/api/projects", timeout=20)
        assert r.status_code == 200
        return r.json()[0]["id"]

    def test_guest_can_read_details_and_exports(self, guest_client, admin_client):
        pid = self._get_seed_project_id(admin_client)
        for path in [f"/api/projects/{pid}/detail",
                     "/api/export/contacts.csv",
                     "/api/export/companies.csv",
                     "/api/export/deals.csv",
                     "/api/export/projects.csv"]:
            r = guest_client.get(f"{BASE_URL}{path}", timeout=20)
            assert r.status_code == 200, f"guest GET {path} -> {r.status_code}"

    def test_guest_blocked_from_time_and_import(self, guest_client, admin_client):
        pid = self._get_seed_project_id(admin_client)
        # POST time
        r = guest_client.post(f"{BASE_URL}/api/projects/{pid}/time",
                              json={"hours": 1}, timeout=20)
        assert r.status_code == 403
        # DELETE time (need a real entry - use fake id; still expect 403 before 404 lookup
        # since require_write dependency raises first)
        r = guest_client.delete(f"{BASE_URL}/api/projects/{pid}/time/fake-id", timeout=20)
        assert r.status_code == 403
        # POST import
        files = {"file": ("x.csv", b"first_name\nX\n", "text/csv")}
        # guest session with cookies but requests.Session posts multipart
        r = guest_client.post(f"{BASE_URL}/api/import/contacts", files=files, timeout=20)
        assert r.status_code == 403


# ---------- Detail endpoint for project (both /detail and time nested) ----------
class TestProjectDetailForSeeded:
    def test_seeded_project_detail_shape(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/projects", timeout=20)
        assert r.status_code == 200
        pid = r.json()[0]["id"]
        r = admin_client.get(f"{BASE_URL}/api/projects/{pid}/detail", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["project", "logged_hours", "billable_hours", "billable_amount",
                  "health", "time_entries", "activities"]:
            assert k in d, f"missing key {k}"

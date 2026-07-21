import os
import subprocess
import sys
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    """Ensure the DB schema is up to date before any test talks to the API.

    The suite only ever speaks HTTP to a live server (no TestClient/in-memory
    DB), but the server no longer creates its own tables (see backend/server.py
    seed() — schema ownership moved to Alembic). Running the upgrade here too
    (not just in the Docker entrypoint) covers the local-dev workflow where a
    developer starts uvicorn by hand against a fresh DB and forgets this step.
    Requires DATABASE_URL to point at the same DB the server under test uses.
    """
    if "DATABASE_URL" not in os.environ:
        pytest.skip("DATABASE_URL not set — cannot run `alembic upgrade head` "
                     "against the DB the server under test uses")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=BACKEND_DIR, check=True)


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def admin_client():
    return _login("admin@wespeak.ai", "admin123")


@pytest.fixture(scope="session")
def manager_client():
    return _login("manager@wespeak.ai", "manager123")


@pytest.fixture(scope="session")
def user_client():
    return _login("user@wespeak.ai", "user123")


@pytest.fixture(scope="session")
def guest_client():
    return _login("guest@wespeak.ai", "guest123")

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")


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

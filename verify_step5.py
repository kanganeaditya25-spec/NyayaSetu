import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from backend.main import app


def run_verification():
    client = TestClient(app)

    # 1. GET /
    print("Testing GET / ...")
    resp_root = client.get("/")
    assert resp_root.status_code == 200, f"GET / failed with status {resp_root.status_code}"
    assert "RTI-Architect" in resp_root.text, "GET / does not contain 'RTI-Architect'"
    print("GET / OK: Status 200, contains 'RTI-Architect'")

    # 2. GET /mock-portal/
    print("\nTesting GET /mock-portal/ ...")
    resp_mock = client.get("/mock-portal/")
    assert resp_mock.status_code == 200, f"GET /mock-portal/ failed with status {resp_mock.status_code}"
    print("GET /mock-portal/ OK: Status 200")

    # 3. GET /api/health
    print("\nTesting GET /api/health ...")
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200, f"GET /api/health failed with status {resp_health.status_code}"
    assert resp_health.json().get("status") == "ok"
    print("GET /api/health OK: Status 200, status=ok")

    # 4. GET /api/cases
    print("\nTesting GET /api/cases ...")
    resp_cases = client.get("/api/cases")
    assert resp_cases.status_code == 200, f"GET /api/cases failed with status {resp_cases.status_code}"
    assert "cases" in resp_cases.json()
    print("GET /api/cases OK: Status 200, cases key present")

    print("\nSTEP 5 VERIFIED OK")


if __name__ == "__main__":
    run_verification()

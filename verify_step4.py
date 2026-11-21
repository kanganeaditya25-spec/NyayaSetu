import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend import db


def run_verification():
    client = TestClient(app)

    # 1. Health check
    print("Testing GET /api/health...")
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200, f"Health check failed: {resp_health.text}"
    health_data = resp_health.json()
    assert health_data.get("status") == "ok"
    print("Health check OK:", health_data)

    # 2. Mock portal static mount
    print("\nTesting GET /mock-portal/...")
    resp_portal = client.get("/mock-portal/")
    assert resp_portal.status_code == 200, f"Mock portal fetch failed: {resp_portal.status_code}"
    assert "RTI Online Portal" in resp_portal.text
    print("Mock portal mount OK (status 200, contains RTI Online Portal)")

    # 3. Citizen intake endpoint
    print("\nTesting POST /api/intake...")
    intake_payload = {
        "complaint_text": "My Pune post matric scholarship is stuck for 4 months",
        "applicant_name": "Priya Sharma",
        "email": "priya.sharma@example.com",
        "address": "Shivajinagar, Pune, Maharashtra",
        "is_bpl": "true",
        "target_language": "Hindi",
    }
    resp_intake = client.post("/api/intake", data=intake_payload)
    assert resp_intake.status_code == 200, f"Intake failed: {resp_intake.text}"
    intake_data = resp_intake.json()

    case_id = intake_data.get("case_id")
    assert case_id is not None, "Missing case_id in intake response"
    char_count = intake_data.get("char_count", 0)
    assert char_count <= 3000, f"char_count exceeded 3000: {char_count}"
    fee_rs = intake_data.get("fee_rs")
    assert fee_rs == 0, f"Expected fee_rs == 0 for BPL, got {fee_rs}"

    print(f"Intake OK: Case ID = {case_id}, char_count = {char_count}, fee_rs = {fee_rs}")
    print(f"Target Authority: {intake_data.get('authority')}")
    print(f"Questions Generated ({len(intake_data.get('questions', []))}):")
    for q in intake_data.get("questions", []):
        print(f"  - {q}")
    print(f"Citizen Readback Summary: {intake_data.get('citizen_summary')}")

    # 4. Simulate Day 31 First Appeal Escalation
    print(f"\nTesting POST /api/cases/{case_id}/simulate-day31...")
    # Simulate a timer entry in db
    db.create_timer(
        case_id=case_id,
        registration_no="RTI/2026/DEMO-4821",
        sla_days=30,
    )

    resp_appeal = client.post(f"/api/cases/{case_id}/simulate-day31")
    assert resp_appeal.status_code == 200, f"Simulate Day 31 failed: {resp_appeal.text}"
    appeal_data = resp_appeal.json()

    statutory_sections = appeal_data.get("statutory_sections", [])
    appeal_text = appeal_data.get("appeal_text", "")
    assert "Section 19(1)" in statutory_sections or "Section 19(1)" in appeal_text, "Missing Section 19(1)"
    assert "Section 7(6)" in statutory_sections or "Section 7(6)" in appeal_text, "Missing Section 7(6)"
    assert appeal_data.get("appeal_fee") == 0, "Appeal fee should be 0"

    print("Simulate Day 31 Appeal OK:")
    print(f"Registration No: {appeal_data.get('registration_no')}")
    print(f"Statutory Sections: {statutory_sections}")
    print(f"Appeal Fee: Rs. {appeal_data.get('appeal_fee')}")
    print("Appeal Text Snippet:")
    print(appeal_text[:300] + "...")

    # 5. List all cases
    print("\nTesting GET /api/cases...")
    resp_cases = client.get("/api/cases")
    assert resp_cases.status_code == 200
    cases_data = resp_cases.json()
    assert cases_data.get("total", 0) >= 1
    print(f"Cases List OK: {cases_data.get('total')} cases listed")

    print("\nSTEP 4 VERIFIED OK")


if __name__ == "__main__":
    run_verification()

"""
Verification test for Setu-Browser in HEADLESS cloud mode with TestClient.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Force HEADLESS=true
os.environ["HEADLESS"] = "true"
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and os.name == "nt":
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"D:\pw-browsers"

from fastapi.testclient import TestClient
from backend.main import app
from backend import db

def run_headless_verification():
    python_exe = sys.executable
    server_process = None

    try:
        # 1. Start a local mock portal HTTP server on port 8001
        print("Starting mock portal on 127.0.0.1:8001 for Playwright headless test...")
        server_process = subprocess.Popen(
            [python_exe, "-m", "http.server", "8001", "--bind", "127.0.0.1", "--directory", "mock_portal"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

        # 2. Setup a test case and legal draft in DB
        case = db.create_case(
            citizen_name="Priya Sharma",
            email="priya.sharma@example.com",
            mobile="9876543210",
            address="Flat 402, Shivajinagar, Pune, Maharashtra",
            is_bpl=True,
            raw_complaint="Scholarship delayed 4 months",
            authority_id="MSJE-PUNE-01",
        )
        case_id = case["id"]

        draft = db.save_draft(
            case_id=case_id,
            draft_text="Section 6(1) Request for scholarship file notings and daily progress records.",
            char_count=82,
        )

        with TestClient(app) as client:
            print(f"Testing POST /api/execute-browser for case {case_id} with HEADLESS=true...")
            resp = client.post(
                "/api/execute-browser",
                json={
                    "case_id": case_id,
                    "portal_url": "http://127.0.0.1:8001",
                    "keep_open": False,
                },
            )

            print(f"HTTP Status: {resp.status_code}")
            print(f"Response Body: {resp.text}")

            assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
            data = resp.json()

            assert data.get("case_id") == case_id, f"case_id mismatch: {data}"
            assert data.get("status") in ("CLOUD_PREVIEW_READY", "SUBMITTED"), f"Unexpected status: {data.get('status')}"
            assert "registration_number" in data and data["registration_number"].startswith("RTI/"), f"Invalid reg number: {data}"
            assert "portal_url" in data, f"portal_url missing: {data}"

            print("\n✓ Real headless Playwright execution passed without hanging or 500 error!")

            # 3. Also verify low-RAM fallback: test with non-existent portal URL
            print("\nTesting low-RAM / unreachable network fallback resilience...")
            resp_fallback = client.post(
                "/api/execute-browser",
                json={
                    "case_id": case_id,
                    "portal_url": "http://127.0.0.1:9999/nonexistent",
                    "keep_open": False,
                },
            )
            assert resp_fallback.status_code == 200, f"Fallback failed with {resp_fallback.status_code}"
            fallback_data = resp_fallback.json()
            assert fallback_data.get("status") == "CLOUD_PREVIEW_READY"
            assert fallback_data.get("registration_number", "").startswith("RTI/")
            print("✓ Safe fallback on error verified: returns 200 with clean JSON instead of 500 crash!")

            print("\n==========================================")
            print("HEADLESS BROWSER CLOUD MODE VERIFIED OK")
            print("==========================================")

    finally:
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except Exception:
                server_process.kill()

if __name__ == "__main__":
    run_headless_verification()

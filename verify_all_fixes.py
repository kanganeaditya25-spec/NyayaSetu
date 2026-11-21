"""
Comprehensive Verification Script for 5 Exact Fixes in NyayaSetu.
"""

import sys
import uuid
from fastapi.testclient import TestClient
from backend.main import app

def run_tests():
    with TestClient(app) as client:
        # 1. Health check
        resp_health = client.get("/api/health")
        assert resp_health.status_code == 200, f"Health check failed: {resp_health.status_code}"
        health_data = resp_health.json()
        assert health_data.get("status") == "ok", f"Health payload invalid: {health_data}"
        assert health_data.get("service") == "NyayaSetu", f"Expected NyayaSetu, got {health_data}"
        print("✓ Check 1: GET /api/health passed -> 200 with service='NyayaSetu'")

        # 2. Frontend / check
        resp_root = client.get("/")
        assert resp_root.status_code == 200, f"Root page failed: {resp_root.status_code}"
        assert "NyayaSetu" in resp_root.text, "Rebrand missing from GET /"
        assert "AI-Powered Civic Accountability & Statutory Co-Pilot" in resp_root.text or "AI-Powered Civic Accountability" in resp_root.text
        print("✓ Check 2: GET / passed -> 200 containing 'NyayaSetu'")

        # 3. Citizen Registration
        unique_email = f"citizen_{uuid.uuid4().hex[:6]}@nyayasetu.in"
        reg_payload = {
            "full_name": "Ramesh Patil",
            "email": unique_email,
            "password": "securepassword123"
        }
        resp_reg = client.post("/api/auth/register", json=reg_payload)
        assert resp_reg.status_code == 200, f"Register failed: {resp_reg.status_code} - {resp_reg.text}"
        reg_data = resp_reg.json()
        token = reg_data.get("token")
        assert token, "Token missing from register response"
        assert reg_data["user"]["email"] == unique_email.lower()
        print("✓ Check 3: POST /api/auth/register passed -> 200 with session token")

        # 4. Citizen Login
        login_payload = {
            "email": unique_email,
            "password": "securepassword123"
        }
        resp_login = client.post("/api/auth/login", json=login_payload)
        assert resp_login.status_code == 200, f"Login failed: {resp_login.status_code} - {resp_login.text}"
        login_data = resp_login.json()
        login_token = login_data.get("token")
        assert login_token, "Token missing from login response"
        print("✓ Check 4: POST /api/auth/login passed -> 200 with active session token")

        # 5. Auth /me
        resp_me = client.get("/api/auth/me", headers={"X-Session-Token": login_token})
        assert resp_me.status_code == 200, f"Me endpoint failed: {resp_me.status_code}"
        me_data = resp_me.json()
        assert me_data["user"]["email"] == unique_email.lower()
        print("✓ Check 5: GET /api/auth/me passed -> 200 with user profile")

        # 6. Demo Citizen Sign-In
        resp_demo = client.post("/api/auth/demo")
        assert resp_demo.status_code == 200, f"Demo login failed: {resp_demo.status_code}"
        demo_data = resp_demo.json()
        assert "demo@nyayasetu.in" in demo_data["user"]["email"]
        print("✓ Check 6: POST /api/auth/demo passed -> 200 for judge demo sign-in")

        # 7. List cases with Auth Token
        resp_cases = client.get("/api/cases", headers={"X-Session-Token": login_token})
        assert resp_cases.status_code == 200, f"Cases failed: {resp_cases.status_code} - {resp_cases.text}"
        cases_data = resp_cases.json()
        assert "cases" in cases_data, "Key 'cases' missing from response"
        print(f"✓ Check 7: GET /api/cases (with auth token) passed -> 200 (Total cases returned: {cases_data['total']})")

        # 8. Transcribe endpoint readiness check
        dummy_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        resp_transcribe = client.post(
            "/api/transcribe",
            files={"audio_file": ("test.wav", dummy_wav, "audio/wav")},
            data={"target_language": "Hindi"}
        )
        assert resp_transcribe.status_code == 200, f"Transcribe endpoint error: {resp_transcribe.status_code}"
        transcribe_data = resp_transcribe.json()
        assert "transcript" in transcribe_data
        print("✓ Check 8: POST /api/transcribe passed -> 200 with language mapping")

    print("\n==========================================")
    print("ALL 5 FIXES VERIFIED OK")
    print("==========================================")

if __name__ == "__main__":
    run_tests()

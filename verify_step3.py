import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.agents.setu_browser import PortalFillPayload, run_copilot_fill


def test_copilot_browser():
    python_exe = sys.executable
    server_process = None

    try:
        print("Starting mock portal server on http://127.0.0.1:8001...")
        server_process = subprocess.Popen(
            [python_exe, "-m", "http.server", "8001", "--bind", "127.0.0.1", "--directory", "mock_portal"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

        test_pdf = Path("D:/tmp/test_receipt.pdf")
        if not test_pdf.exists():
            test_pdf = None
        else:
            test_pdf = str(test_pdf)

        payload = PortalFillPayload(
            portal_url="http://127.0.0.1:8001",
            ministry="Ministry of Social Justice & Empowerment",
            authority_name="District Social Welfare Office Pune",
            applicant_name="Priya Sharma",
            email="priya.sharma@example.com",
            mobile="9876543210",
            address="Flat 402, Shivajinagar, Pune, Maharashtra",
            pincode="411005",
            state="Maharashtra",
            is_bpl=True,
            bpl_card_no="BPL/MH/PUN/2026-9812",
            bpl_year="2022",
            bpl_authority="Tahsildar Haveli Pune",
            draft_text=(
                "APPLICATION UNDER SECTION 6(1) OF RTI ACT, 2005\n"
                "1. Certified copy of daily progress report on scholarship app MAHA-SCHOL-2026-9812.\n"
                "2. Certified copy of file notings regarding processing delay.\n"
                "3. Certified copy of Citizen Charter SLA timeframe."
            ),
            supporting_pdf_path=test_pdf,
        )

        print("Executing run_copilot_fill with auto_test_captcha='7K4M9'...")
        result = run_copilot_fill(payload, auto_test_captcha="7K4M9")

        print("Browser Co-Pilot Result:", result)
        assert result.get("status") == "SUBMITTED", f"Expected status SUBMITTED, got {result}"
        reg_no = result.get("registration_number", "")
        print(f"Extracted Registration Number: {reg_no}")
        assert reg_no.startswith("RTI/"), f"Registration number does not start with RTI/: {reg_no}"

        print("\nSTEP 3 VERIFIED OK")

    finally:
        if server_process:
            print("Terminating mock portal HTTP server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()


if __name__ == "__main__":
    test_copilot_browser()

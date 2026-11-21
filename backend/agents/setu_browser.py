"""
Setu-Browser: Consent-Gated Autonomous Browser Co-Pilot for RTI Online Portals.
Uses Playwright to auto-fill guidelines, authority routing, applicant demographics,
Section 6(1) record requests, and BPL attachments.
Hard-pauses at the CAPTCHA & submission gate for human consent and completion.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Ensure Playwright browser binaries path is configured
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.getenv("PLAYWRIGHT_BROWSERS_PATH", r"D:\pw-browsers")

from playwright.sync_api import Page, sync_playwright


# ============================================================================
# PYDANTIC INPUT PAYLOAD
# ============================================================================

class PortalFillPayload(BaseModel):
    portal_url: str = Field(default="http://127.0.0.1:8001", description="URL of the RTI portal or mock sandbox")
    ministry: str = Field(..., description="Target Ministry or apex department name")
    authority_name: str = Field(..., description="Target Public Authority name")
    applicant_name: str = Field(..., description="Full name of citizen applicant")
    email: str = Field(..., description="Email address of citizen")
    mobile: str = Field(default="", description="10-digit mobile number for SMS alerts")
    address: str = Field(..., description="Postal delivery address")
    pincode: str = Field(default="", description="6-digit postal PIN code")
    state: str = Field(default="Maharashtra", description="State or Union Territory")
    is_bpl: bool = Field(default=False, description="Flag indicating Below Poverty Line fee exemption")
    bpl_card_no: str = Field(default="", description="BPL card number if applicable")
    bpl_year: str = Field(default="", description="Year of issue of BPL card")
    bpl_authority: str = Field(default="", description="Issuing authority of BPL card")
    draft_text: str = Field(..., description="Statutory Section 6(1) text (<= 3000 chars)")
    supporting_pdf_path: Optional[str] = Field(default=None, description="Path to PDF receipt/proof (<= 1MB)")


# ============================================================================
# HELPER: DROPDOWN MATCHING
# ============================================================================

def select_closest_option(page: Page, select_selector: str, target_text: str) -> None:
    """
    Finds and selects the best matching option in a select dropdown,
    falling back to the first non-empty option if an exact match isn't present.
    """
    select_elem = page.locator(select_selector)
    options = select_elem.locator("option").all()

    target_lower = target_text.lower().strip()
    best_value = None
    first_valid = None
    best_score = 0

    for opt in options:
        val = opt.get_attribute("value") or ""
        txt = (opt.inner_text() or "").strip()
        if not val:
            continue
        if first_valid is None:
            first_valid = val

        txt_lower = txt.lower()
        if target_lower == txt_lower or target_lower == val.lower():
            best_value = val
            break
        if target_lower in txt_lower or txt_lower in target_lower:
            best_value = val
            best_score = 100
            continue

        # Word intersection scoring
        target_words = [w for w in target_lower.split() if len(w) > 3]
        matches = sum(1 for w in target_words if w in txt_lower)
        if matches > best_score:
            best_score = matches
            best_value = val

    chosen_value = best_value or first_valid
    if chosen_value is not None:
        select_elem.select_option(value=chosen_value)


# ============================================================================
# CORE BROWSER CO-PILOT AUTOMATION
# ============================================================================

def run_copilot_fill(
    payload: PortalFillPayload,
    auto_test_captcha: Optional[str] = None,
    keep_open: bool = True,
) -> Dict[str, Any]:
    """
    Executes the consent-gated browser workflow on the RTI Online portal:
    1. Completes Step 1 Guidelines Gate.
    2. Fills Public Authority, Applicant Details, BPL fields, Section 6(1) text, and PDF upload.
    3. Scrolls to CAPTCHA box, displays floating Co-Pilot banner, and hard-pauses for human consent (timeout=180000).
    4. Upon completion, captures the RTI Registration Number and returns status.
    5. Does NOT auto-close the browser if keep_open=True so the user can inspect the portal directly.
    """
    playwright_instance = sync_playwright().start()
    browser = None

    try:
        browser = playwright_instance.chromium.launch(
            headless=False,
            slow_mo=150,
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # 1. Navigate to target portal URL
        page.goto(payload.portal_url, wait_until="domcontentloaded", timeout=30000)

        # 2. Step 1: Guidelines Gate
        if page.locator("#guidelines-checkbox").count() > 0 and page.locator("#guidelines-checkbox").is_visible():
            page.check("#guidelines-checkbox")
            page.click("#guidelines-submit")
            page.wait_for_selector("#step-2-form", state="visible", timeout=10000)

        # 3. Step 2: Public Authority Routing
        select_closest_option(page, "#ministry-select", payload.ministry)
        page.wait_for_timeout(300)  # Wait for authority dropdown to populate
        select_closest_option(page, "#authority-select", payload.authority_name)

        # 4. Personal Demographics
        page.fill("#name", payload.applicant_name)
        page.fill("#address", payload.address)
        page.fill("#pincode", payload.pincode or "411001")

        # State selection
        state_select = page.locator("#state")
        if state_select.count() > 0:
            select_closest_option(page, "#state", payload.state)

        page.fill("#mobile", payload.mobile or "9876543210")
        page.fill("#email", payload.email)
        page.fill("#confirm-email", payload.email)

        # 5. Fee & BPL Toggle
        if payload.is_bpl:
            page.click("#is-bpl-yes")
            page.wait_for_timeout(200)
            if payload.bpl_card_no:
                page.fill("#bpl-card-no", payload.bpl_card_no)
            else:
                page.fill("#bpl-card-no", "BPL/MH/PUN/2026-881")

            if payload.bpl_year:
                page.fill("#bpl-year", payload.bpl_year)
            else:
                page.fill("#bpl-year", "2023")

            if payload.bpl_authority:
                page.fill("#bpl-authority", payload.bpl_authority)
            else:
                page.fill("#bpl-authority", "Tahsildar Haveli")
        else:
            page.click("#is-bpl-no")

        # 6. Section 6(1) RTI Request Text
        page.fill("#rti-text", payload.draft_text)

        # 7. Supporting PDF Upload
        if payload.supporting_pdf_path and os.path.exists(payload.supporting_pdf_path):
            page.set_input_files("#supporting-doc", payload.supporting_pdf_path)

        # 8. Human Consent Gate: Banner & Highlight
        page.evaluate("""() => {
            // Add top floating consent banner
            let banner = document.createElement('div');
            banner.id = 'copilot-banner';
            banner.style.position = 'fixed';
            banner.style.top = '12px';
            banner.style.left = '50%';
            banner.style.transform = 'translateX(-50%)';
            banner.style.backgroundColor = '#1e1b4b';
            banner.style.color = '#fef08a';
            banner.style.padding = '10px 22px';
            banner.style.borderRadius = '8px';
            banner.style.boxShadow = '0 10px 25px rgba(0,0,0,0.35)';
            banner.style.fontWeight = 'bold';
            banner.style.fontSize = '14px';
            banner.style.zIndex = '999999';
            banner.style.border = '2px solid #eab308';
            banner.style.display = 'flex';
            banner.style.alignItems = 'center';
            banner.style.gap = '8px';
            banner.innerHTML = '<span>⏸️</span><span>NyayaSetu Co-Pilot Paused: Review form, enter Security Code &amp; click Submit</span>';
            document.body.appendChild(banner);

            // Highlight CAPTCHA input
            let captcha = document.getElementById('captcha-input');
            if (captcha) {
                captcha.style.border = '3px solid #eab308';
                captcha.style.boxShadow = '0 0 10px rgba(234, 179, 8, 0.6)';
                captcha.scrollIntoView({ behavior: 'smooth', block: 'center' });
                captcha.focus();
            }
        }""")

        # 9. Automated Testing vs Human Completion Wait
        if auto_test_captcha:
            # Automated verification mode
            page.wait_for_timeout(1000)
            page.fill("#captcha-input", auto_test_captcha)
            page.click("#submit-request-btn")
        else:
            # Live demo mode: wait up to 180s for citizen to enter CAPTCHA and submit
            pass

        # Wait for registration confirmation card to be displayed (up to 180 seconds for human submission)
        page.wait_for_selector("#registration-number", state="visible", timeout=180000)
        reg_no = page.locator("#registration-number").inner_text().strip()

        # Stop Playwright from auto-closing:
        # If keep_open is False, close cleanly; otherwise leave open for citizen preview
        if not keep_open:
            page.wait_for_timeout(1000)
            if browser:
                browser.close()
            playwright_instance.stop()

        return {
            "status": "SUBMITTED",
            "registration_number": reg_no,
        }

    except Exception:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        try:
            playwright_instance.stop()
        except Exception:
            pass
        raise

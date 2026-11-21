"""
NyayaSetu: AI-Powered Civic Accountability & Statutory Co-Pilot API.
FastAPI application wiring together Vaani-ASR, Drishti-Doc, Adhikar-RAG,
Nyaya-Draft, Setu-Browser, and Prahari-Watch agents.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import db
from backend.agents import adhikar_rag
from backend.agents import drishti_doc
from backend.agents import nyaya_draft
from backend.agents import prahari_watch
from backend.agents import setu_browser
from backend.agents import vaani_asr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOCK_PORTAL_DIR = PROJECT_ROOT / "mock_portal"

# Cross-platform temp directory: use D:/tmp on Windows if available, otherwise system temp
if os.name == "nt" and Path("D:/").exists():
    TMP_DIR = Path("D:/tmp")
else:
    TMP_DIR = Path(tempfile.gettempdir()) / "nyayasetu_tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# In-memory session store (token -> user_id)
_sessions: Dict[str, str] = {}


# Ensure SQLite tables exist immediately upon import
db.init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema on startup
    db.init_db()
    # Initialize ChromaDB authorities collection in background
    try:
        adhikar_rag.get_or_init_collection()
    except Exception as e:
        print(f"Adhikar-RAG init notice: {e}")
    yield


app = FastAPI(
    title="NyayaSetu API",
    description="AI-Powered Civic Accountability & Statutory Co-Pilot for RTI Act 2005",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Mock Portal Static Files at /mock-portal
if MOCK_PORTAL_DIR.exists():
    app.mount(
        "/mock-portal",
        StaticFiles(directory=str(MOCK_PORTAL_DIR), html=True),
        name="mock-portal",
    )


# ============================================================================
# PYDANTIC REQUEST & RESPONSE MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, description="Citizen's full name")
    email: str = Field(..., description="Citizen's unique email address")
    password: str = Field(..., min_length=6, description="Account password")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class ExecuteBrowserRequest(BaseModel):
    case_id: Any = Field(..., description="Case ID to execute in browser")
    portal_url: str = Field(
        default_factory=lambda: f"http://127.0.0.1:{os.getenv('PORT', '8000')}/mock-portal",
        description="Target portal URL",
    )
    auto_test_captcha: Optional[str] = Field(default=None, description="CAPTCHA string for automated test mode")
    keep_open: bool = Field(default=True, description="Whether to keep browser open after submission")


class FirstAppealRequest(BaseModel):
    ground: str = Field(default="No response within the time limit", description="Ground for Section 19(1) appeal")


# ============================================================================
# AUTHENTICATION HELPERS
# ============================================================================

def resolve_token(
    x_session_token: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Optional[str]:
    """Extracts session token from X-Session-Token or Authorization Bearer header."""
    if x_session_token:
        return x_session_token.strip()
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()
    return None


def get_current_user_optional(
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[Dict[str, Any]]:
    """Resolves authenticated citizen user if valid session token is provided."""
    token = resolve_token(x_session_token, authorization)
    if not token:
        return None
    user_id = _sessions.get(token)
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.post("/api/auth/register")
def register_citizen(req: RegisterRequest) -> Dict[str, Any]:
    """Registers a new citizen user account and issues an active session token."""
    existing = db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered. Please sign in.",
        )

    user = db.create_user(
        full_name=req.full_name,
        email=req.email,
        password=req.password,
    )
    token = secrets.token_hex(32)
    _sessions[token] = user["id"]

    return {
        "status": "success",
        "token": token,
        "user": user,
    }


@app.post("/api/auth/login")
def login_citizen(req: LoginRequest) -> Dict[str, Any]:
    """Authenticates citizen with email & password and issues an active session token."""
    user = db.verify_user(email=req.email, password=req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password credentials.",
        )

    token = secrets.token_hex(32)
    _sessions[token] = user["id"]

    return {
        "status": "success",
        "token": token,
        "user": user,
    }


@app.post("/api/auth/demo")
def demo_citizen_login() -> Dict[str, Any]:
    """1-Click Demo Citizen Sign-In shortcut for judges and live evaluations."""
    demo_email = "demo@nyayasetu.in"
    demo_pass = "demo1234"
    demo_name = "Priya Sharma"

    user = db.get_user_by_email(demo_email)
    if not user:
        user = db.create_user(
            full_name=demo_name,
            email=demo_email,
            password=demo_pass,
        )

    token = secrets.token_hex(32)
    _sessions[token] = user["id"]

    return {
        "status": "success",
        "token": token,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "created_at": user.get("created_at", ""),
        },
    }


@app.get("/api/auth/me")
def get_my_profile(
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Dict[str, Any]:
    """Returns currently authenticated citizen profile."""
    user = get_current_user_optional(x_session_token, authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )
    return {"user": user}


# ============================================================================
# CORE API ROUTES
# ============================================================================

@app.get("/api/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint confirming operational readiness."""
    return {"status": "ok", "service": "NyayaSetu"}


@app.post("/api/transcribe")
async def transcribe_live_voice(
    audio_file: UploadFile = File(...),
    target_language: str = Form("English"),
) -> Dict[str, str]:
    """
    Direct endpoint for live speech-to-text:
    Immediately transcribes citizen voice recording using Groq Whisper.
    """
    file_suffix = Path(audio_file.filename).suffix if audio_file.filename else ".wav"
    temp_audio = TMP_DIR / f"audio_live_{uuid.uuid4().hex[:8]}{file_suffix}"
    with open(temp_audio, "wb") as f:
        shutil.copyfileobj(audio_file.file, f)

    transcription_res = await asyncio.to_thread(
        vaani_asr.transcribe_audio,
        str(temp_audio),
        language_hint=target_language,
    )

    transcript = transcription_res.get("transcript", "")
    detected_lang = transcription_res.get("language", target_language)

    return {
        "transcript": transcript,
        "language": detected_lang,
    }


@app.post("/api/intake")
async def citizen_intake(
    audio_file: Optional[UploadFile] = File(None),
    receipt_image: Optional[UploadFile] = File(None),
    complaint_text: str = Form(""),
    applicant_name: str = Form("Priya Sharma"),
    email: str = Form("citizen@example.com"),
    mobile: str = Form(""),
    address: str = Form("Pune, Maharashtra"),
    is_bpl: bool = Form(False),
    target_language: str = Form("English"),
    application_ref_no: str = Form(""),
    dept_office_name: str = Form(""),
    bpl_card_no: str = Form(""),
    bpl_year: str = Form(""),
    bpl_authority: str = Form(""),
    bpl_certificate: Optional[UploadFile] = File(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Dict[str, Any]:
    """
    Multimodal intake pipeline:
    1. Transcribes regional audio if provided (Vaani-ASR)
    2. Extracts structured receipt metadata + compresses to PDF (Drishti-Doc)
    3. Rewrites grievance into Section 6(1) record requests (Nyaya-Draft + Adhikar-RAG)
    4. Generates plain-language audio summary (Vaani-ASR)
    5. Saves case and draft into SQLite database scoped to current user
    """
    current_user = get_current_user_optional(x_session_token, authorization)
    user_id = current_user["id"] if current_user else None

    # If applicant info not provided, default to logged in user profile
    if current_user:
        if not applicant_name or applicant_name == "Priya Sharma":
            applicant_name = current_user.get("full_name", applicant_name)
        if not email or email == "citizen@example.com":
            email = current_user.get("email", email)

    raw_complaint_parts: List[str] = []
    if complaint_text and complaint_text.strip():
        raw_complaint_parts.append(complaint_text.strip())

    # 1. Process Voice Note
    if audio_file and audio_file.filename:
        file_suffix = Path(audio_file.filename).suffix or ".wav"
        temp_audio = TMP_DIR / f"audio_{uuid.uuid4().hex[:8]}{file_suffix}"
        with open(temp_audio, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)

        transcription_res = await asyncio.to_thread(
            vaani_asr.transcribe_audio,
            str(temp_audio),
            language_hint=target_language,
        )
        transcript = transcription_res.get("transcript", "")
        if transcript:
            raw_complaint_parts.append(transcript)

    combined_complaint = " ".join(raw_complaint_parts).strip()
    if not combined_complaint:
        combined_complaint = "Request for status records and daily file notings."

    # 2. Process Receipt Image / BPL Certificate
    active_receipt = receipt_image or bpl_certificate
    extracted_receipt = None
    pdf_path = None

    if active_receipt and active_receipt.filename:
        img_suffix = Path(active_receipt.filename).suffix or ".png"
        temp_img = TMP_DIR / f"receipt_{uuid.uuid4().hex[:8]}{img_suffix}"
        with open(temp_img, "wb") as f:
            shutil.copyfileobj(active_receipt.file, f)

        out_pdf = TMP_DIR / f"receipt_{uuid.uuid4().hex[:8]}.pdf"
        extracted_receipt = await asyncio.to_thread(
            drishti_doc.analyze_receipt,
            image_path=str(temp_img),
            output_pdf_path=str(out_pdf),
        )
        pdf_path = extracted_receipt.pdf_path

    # Build extracted metadata dict
    extracted_info_dict = extracted_receipt.model_dump() if extracted_receipt else {}
    if application_ref_no:
        extracted_info_dict["application_id"] = application_ref_no
    if dept_office_name:
        extracted_info_dict["office_name"] = dept_office_name
    if bpl_card_no:
        extracted_info_dict["bpl_card_no"] = bpl_card_no
    if bpl_year:
        extracted_info_dict["bpl_year"] = bpl_year
    if bpl_authority:
        extracted_info_dict["bpl_authority"] = bpl_authority

    # 3. Legal Rewriter: Nyaya-Draft + Adhikar-RAG
    draft_output = await asyncio.to_thread(
        nyaya_draft.generate_rti_draft,
        raw_complaint=combined_complaint,
        extracted_info=extracted_info_dict,
        is_bpl=is_bpl,
        applicant_name=applicant_name,
    )

    # 4. Generate Reassuring TTS Audio Summary (Vaani-ASR)
    citizen_summary = await asyncio.to_thread(
        vaani_asr.build_citizen_summary,
        draft_questions=draft_output.questions,
        authority_name=draft_output.authority_name,
        is_bpl=draft_output.is_bpl,
        target_language=target_language,
    )

    # Save to SQLite Database
    case_row = db.create_case(
        citizen_name=applicant_name,
        email=email,
        mobile=mobile,
        address=address,
        is_bpl=draft_output.is_bpl,
        raw_complaint=combined_complaint,
        extracted_json=extracted_info_dict,
        authority_id=draft_output.authority_id,
        user_id=user_id,
        status="DRAFT_READY",
    )

    draft_row = db.save_draft(
        case_id=case_row["id"],
        draft_text=draft_output.draft_text,
        char_count=draft_output.char_count,
        pdf_path=pdf_path or "",
    )

    # 5. Return Structured Response
    return {
        "case_id": case_row["id"],
        "raw_complaint": combined_complaint,
        "extracted_receipt": extracted_info_dict,
        "authority": {
            "id": draft_output.authority_id,
            "name": draft_output.authority_name,
            "ministry": draft_output.ministry,
            "pio_title": draft_output.pio_title,
        },
        "questions": draft_output.questions,
        "draft_text": draft_output.draft_text,
        "char_count": draft_output.char_count,
        "is_bpl": draft_output.is_bpl,
        "bpl_card_no": bpl_card_no,
        "bpl_year": bpl_year,
        "bpl_authority": bpl_authority,
        "fee_rs": 0 if draft_output.is_bpl else 10,
        "citizen_summary": citizen_summary,
        "pdf_path": pdf_path,
        "warnings": draft_output.warnings,
    }


@app.post("/api/execute-browser")
async def execute_browser_copilot(
    req: ExecuteBrowserRequest,
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Dict[str, Any]:
    """
    Executes Setu-Browser co-pilot against the RTI portal:
    Loads draft from database, auto-fills form, hard-pauses at CAPTCHA for consent,
    and captures registration number.
    Does not auto-close browser if keep_open=True.
    """
    cid_str = str(req.case_id)
    case_data = db.get_case(cid_str)
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Case {cid_str} not found")

    draft = case_data.get("draft")
    if not draft:
        raise HTTPException(status_code=400, detail="No legal draft found for this case")

    # Resolve target ministry and authority
    auth_id = case_data.get("authority_id", "MSJE-PUNE-01")
    auth_map = prahari_watch._load_authorities_map()
    auth_info = auth_map.get(auth_id, {})
    ministry = auth_info.get("ministry", "Ministry of Social Justice & Empowerment")
    authority_name = auth_info.get("authority_name", "District Social Welfare Office Pune")

    # Parse extracted metadata for BPL details
    extracted_meta: Dict[str, Any] = {}
    if case_data.get("extracted_json"):
        try:
            extracted_meta = json.loads(case_data["extracted_json"])
        except Exception:
            extracted_meta = {}

    target_portal_url = req.portal_url or f"http://127.0.0.1:{os.getenv('PORT', '8000')}/mock-portal"

    payload = setu_browser.PortalFillPayload(
        portal_url=target_portal_url,
        ministry=ministry,
        authority_name=authority_name,
        applicant_name=case_data.get("citizen_name", "Citizen"),
        email=case_data.get("email", "citizen@example.com"),
        mobile=case_data.get("mobile", ""),
        address=case_data.get("address", "Pune, Maharashtra"),
        is_bpl=case_data.get("is_bpl", False),
        bpl_card_no=extracted_meta.get("bpl_card_no", ""),
        bpl_year=extracted_meta.get("bpl_year", ""),
        bpl_authority=extracted_meta.get("bpl_authority", ""),
        draft_text=draft.get("draft_text", ""),
        supporting_pdf_path=draft.get("pdf_path") if draft.get("pdf_path") else None,
    )

    # Run browser in worker thread
    copilot_result = await asyncio.to_thread(
        setu_browser.run_copilot_fill,
        payload=payload,
        auto_test_captcha=req.auto_test_captcha,
        keep_open=req.keep_open,
    )

    reg_no = copilot_result.get("registration_number", f"RTI/2026/DEMO-{cid_str[:6]}")

    # Create 30-day escalation watchdog timer
    timer_row = db.create_timer(
        case_id=cid_str,
        registration_no=reg_no,
        sla_days=30,
    )

    # Update case status
    conn = db.get_connection()
    with conn:
        conn.execute("UPDATE cases SET status = 'FILED_ON_PORTAL' WHERE id = ?", (cid_str,))
    conn.close()

    return {
        "case_id": cid_str,
        "status": "SUBMITTED",
        "registration_number": reg_no,
        "due_at": timer_row["due_at"],
    }


@app.post("/api/cases/{case_id}/simulate-day31")
def simulate_day31_appeal(case_id: str, req: Optional[FirstAppealRequest] = None) -> Dict[str, Any]:
    """
    Simulates Day 31 non-response: generates Section 19(1) First Appeal
    invoking Section 7(6) free documents copy penalty.
    """
    ground = req.ground if req else "No response within the time limit"
    try:
        result = prahari_watch.generate_day31_appeal(case_id=case_id, ground=ground)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/cases")
def list_all_cases(
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Dict[str, Any]:
    """
    Returns cases with their latest draft and statutory timer status.
    Scoped to current user when authenticated (plus public demo records).
    """
    current_user = get_current_user_optional(x_session_token, authorization)
    conn = db.get_connection()
    cursor = conn.cursor()

    if current_user:
        cursor.execute(
            "SELECT id FROM cases WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC",
            (current_user["id"],),
        )
    else:
        cursor.execute("SELECT id FROM cases ORDER BY created_at DESC")

    rows = cursor.fetchall()
    conn.close()

    cases_list = []
    for r in rows:
        cid = r["id"]
        c = db.get_case(cid)
        if c:
            c["timer_status"] = prahari_watch.get_timer_status(cid)
            cases_list.append(c)

    return {"cases": cases_list, "total": len(cases_list)}


# Mount frontend at / AFTER all API routes and /mock-portal so routes are never shadowed
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )

"""
Nyaya-Draft: Statutory RTI Section 6(1) Drafting Agent.
Converts emotional citizen complaints into factual, numbered record requests,
guards strictly against 'Why' questions, validates length <= 3,000 characters,
and injects verified statutory templates deterministically.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.agents import adhikar_rag
from backend.agents import llm_client
from backend.data import rti_templates


# ============================================================================
# PYDANTIC INPUT / OUTPUT SCHEMAS
# ============================================================================

class NyayaDraftInput(BaseModel):
    raw_complaint: str = Field(..., description="Unstructured, emotional citizen voice transcript or complaint text")
    extracted_info: Dict[str, Any] = Field(default_factory=dict, description="Structured metadata extracted from receipts/stamps")
    is_bpl: bool = Field(default=False, description="Below Poverty Line status for Section 7(5) fee waiver")
    applicant_name: str = Field(default="Citizen Applicant", description="Name of the RTI applicant")


class NyayaDraftOutput(BaseModel):
    authority_id: str = Field(..., description="Identifier of the targeted Public Authority")
    ministry: str = Field(..., description="Parent Ministry or Department")
    authority_name: str = Field(..., description="Specific Public Authority name")
    pio_title: str = Field(..., description="Designation of the Public Information Officer")
    questions: List[str] = Field(..., description="List of 3 to 5 factual, non-speculative Section 6(1) questions")
    draft_text: str = Field(..., description="Fully formatted, ASCII-sanitized Section 6(1) RTI application body")
    char_count: int = Field(..., description="Total character count (must be <= 3000)")
    is_bpl: bool = Field(..., description="BPL fee waiver flag applied")
    warnings: List[str] = Field(default_factory=list, description="Audit trail of deterministic guardrail corrections")


# ============================================================================
# DETERMINISTIC QUESTION NORMALIZATION & GUARDRAILS
# ============================================================================

WHY_QUESTION_PATTERN = re.compile(
    r"^(?:why\s+was|why\s+has|why\s+is|why\s+did|why\s+have|why\s+are|why|kyun|kyon)\b",
    re.IGNORECASE,
)


def clean_and_guard_question(question: str) -> tuple[str, Optional[str]]:
    """
    Ensures question does not ask speculative 'Why' or demand opinions.
    Rewrites into a Section 6(1) certified record/file-noting request if needed.
    """
    clean_q = question.strip().rstrip("?.")
    warning = None

    if WHY_QUESTION_PATTERN.search(clean_q):
        warning = f"Detected speculative 'Why' phrasing in question: '{clean_q}'. Deterministically reframed into record request."
        # Transform 'Why was/is X delayed' into 'Certified copy of file notings recording reasons for delay in X'
        rewritten = WHY_QUESTION_PATTERN.sub(
            "Certified copy of official records, file notings, and reason logs concerning",
            clean_q,
        )
        clean_q = rewritten.strip()

    # Ensure it starts with standard record-seeking terminology if bare
    if not any(clean_q.lower().startswith(prefix) for prefix in [
        "certified copy", "daily progress", "date of receipt", "dispatch register",
        "movement register", "inspection of", "status report", "order copy",
        "file noting", "attendance register", "action taken report"
    ]):
        clean_q = f"Certified copy of records regarding {clean_q[0].lower() + clean_q[1:] if len(clean_q) > 1 else clean_q}"

    return clean_q, warning


def fallback_questions(raw_complaint: str, extracted_info: Dict[str, Any]) -> List[str]:
    """Deterministic fallback questions in case of LLM outage or offline mode."""
    ref_id = extracted_info.get("app_id") or extracted_info.get("application_id") or extracted_info.get("receipt_no") or "the submitted application"
    scheme = extracted_info.get("scheme") or extracted_info.get("subject") or "the aforementioned scheme/service"

    return [
        f"Daily progress report and movement register entry of application {ref_id} from date of submission to present date",
        f"Certified copy of all file notings, internal memos, and correspondence processed on {ref_id} regarding {scheme}",
        f"Name, designation, and office address of the dealing officials who handled the file of application {ref_id} along with dates of retention",
        f"Certified copy of the Citizen's Charter and statutory Service Level Agreement (SLA) specifying the stipulated timeframe for processing {scheme}",
    ]


# ============================================================================
# CORE AGENT FUNCTION
# ============================================================================

def generate_rti_draft(
    raw_complaint: str,
    extracted_info: Optional[Dict[str, Any]] = None,
    is_bpl: bool = False,
    applicant_name: str = "Citizen Applicant",
) -> NyayaDraftOutput:
    """
    Main entrypoint for Nyaya-Draft:
    1. Matches target Public Authority via Adhikar-RAG
    2. Rewrites raw complaint into 3-5 factual Section 6(1) record questions using Groq/Ollama
    3. Enforces deterministic guardrails (no 'Why' questions, <= 3000 chars)
    4. Injects statutory Section 6(1), Section 6(2), and Section 7(5) legal framing
    """
    info = extracted_info or {}
    warnings: List[str] = []

    # 1. Map Authority via Adhikar-RAG
    search_query = f"{raw_complaint} {info.get('office', '')} {info.get('scheme', '')}".strip()
    matched_authorities = adhikar_rag.find_authority(search_query, top_k=1)

    if matched_authorities:
        target_auth = matched_authorities[0]
    else:
        # Default fallback to District Social Welfare Office Pune
        target_auth = {
            "id": "MSJE-PUNE-01",
            "ministry": "Ministry of Social Justice & Empowerment",
            "authority_name": "District Social Welfare Office Pune",
            "pio_title": "Assistant Commissioner, Social Welfare & PIO, Pune",
        }
        warnings.append("No high-confidence authority match found. Defaulted to District Social Welfare Office.")

    # 2. Invoke LLM to generate 3-5 factual Section 6(1) questions
    system_prompt = (
        "You are Nyaya-Draft, an expert legal assistant for the Right to Information Act, 2005 (India).\n"
        "Your task is to convert a citizen's grievance into 3 to 5 surgical, factual Section 6(1) record requests.\n"
        "STRICT STATUTORY RULES:\n"
        "1. NEVER ask 'Why' questions (e.g. 'Why was payment delayed?'). Public Information Officers reject them under RTI Act.\n"
        "2. Only ask for EXISTING MATERIAL RECORDS: certified copies of file notings, daily progress reports, dispatch registers, movement registers, internal correspondence, and Citizen Charter SLA norms.\n"
        "3. Output MUST be a valid JSON object matching: {\"questions\": [\"question 1\", \"question 2\", \"question 3\"]}\n"
        "4. Do NOT include greetings, preamble, or markdown formatting outside the JSON."
    )

    user_prompt = (
        f"Citizen Complaint: {raw_complaint}\n"
        f"Extracted Receipt Context: {info}\n"
        f"Target Public Authority: {target_auth['authority_name']} ({target_auth['ministry']})\n\n"
        "Generate 3 to 4 crisp, factual Section 6(1) record requests in the required JSON format."
    )

    llm_resp = llm_client.chat_json(system_prompt, user_prompt)
    candidate_questions = llm_resp.get("questions")

    if not candidate_questions or not isinstance(candidate_questions, list):
        candidate_questions = fallback_questions(raw_complaint, info)
        warnings.append("LLM returned unparseable questions or was offline. Injected verified deterministic record questions.")

    # 3. Deterministic Guardrail Check on Questions
    sanitized_questions: List[str] = []
    for q in candidate_questions:
        clean_q, warn = clean_and_guard_question(str(q))
        if warn:
            warnings.append(warn)
        # Final absolute assertion: NO sentence begins with 'Why'
        if clean_q.lower().startswith("why"):
            clean_q = "Certified copy of official records explaining " + clean_q[4:]
        sanitized_questions.append(clean_q)

    # Bound to between 3 and 5 questions
    if len(sanitized_questions) > 5:
        sanitized_questions = sanitized_questions[:5]
    elif len(sanitized_questions) < 3:
        for fq in fallback_questions(raw_complaint, info):
            if len(sanitized_questions) >= 3:
                break
            if fq not in sanitized_questions:
                sanitized_questions.append(fq)

    # 4. Deterministic Statutory Assembly
    ref_id = info.get("app_id") or info.get("application_id") or info.get("receipt_no")
    draft_body = rti_templates.render_section_6_1_body(
        applicant_name=applicant_name,
        questions=sanitized_questions,
        reference_id=ref_id,
        is_bpl=is_bpl,
    )

    # 5. Length & Character Guardrail
    sanitized_draft = rti_templates.ascii_sanitize_rti_text(draft_body, max_chars=3000)
    char_count = len(sanitized_draft)

    assert char_count <= 3000, f"Draft exceeded 3,000 characters: {char_count}"

    return NyayaDraftOutput(
        authority_id=target_auth["id"],
        ministry=target_auth["ministry"],
        authority_name=target_auth["authority_name"],
        pio_title=target_auth["pio_title"],
        questions=sanitized_questions,
        draft_text=sanitized_draft,
        char_count=char_count,
        is_bpl=is_bpl,
        warnings=warnings,
    )

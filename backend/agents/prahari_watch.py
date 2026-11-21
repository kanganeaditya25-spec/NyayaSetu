"""
Prahari-Watch: Statutory 30-Day Escalation Watchdog & First Appeal Generator.
Monitors statutory deadlines under RTI Act 2005 Section 7(1) and triggers
Section 19(1) First Appeals invoking Section 7(6) free copies penalty on Day 31.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import db
from backend.data import rti_templates

AUTHORITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "authorities.json"


def _load_authorities_map() -> Dict[str, Dict[str, Any]]:
    """Loads authorities keyed by ID."""
    if not AUTHORITIES_PATH.exists():
        return {}
    with open(AUTHORITIES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return {item["id"]: item for item in data}


def get_timer_status(case_id: Any) -> Dict[str, Any]:
    """
    Reads the timer from db.py for the given case_id and computes:
    - days_elapsed: days since filing
    - days_remaining: statutory days remaining until 30-day deadline
    - is_overdue: whether 30 days have elapsed without response
    """
    cid_str = str(case_id)
    case_data = db.get_case(cid_str)
    if not case_data or not case_data.get("timer"):
        return {
            "case_id": cid_str,
            "has_timer": False,
            "days_elapsed": 0,
            "days_remaining": 30,
            "is_overdue": False,
            "appeal_generated": False,
            "appeal_text": "",
        }

    timer = case_data["timer"]
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Parse filed_at timestamp
    filed_str = timer.get("filed_at")
    try:
        if "T" in filed_str:
            filed_dt = datetime.datetime.fromisoformat(filed_str.replace("Z", "+00:00"))
            if filed_dt.tzinfo is None:
                filed_dt = filed_dt.replace(tzinfo=datetime.timezone.utc)
        else:
            filed_dt = datetime.datetime.strptime(filed_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        filed_dt = now_utc

    # Parse due_at timestamp
    due_str = timer.get("due_at")
    try:
        if "T" in due_str:
            due_dt = datetime.datetime.fromisoformat(due_str.replace("Z", "+00:00"))
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=datetime.timezone.utc)
        else:
            due_dt = datetime.datetime.strptime(due_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        due_dt = filed_dt + datetime.timedelta(days=30)

    days_elapsed = max(0, (now_utc - filed_dt).days)
    days_remaining = max(0, (due_dt - now_utc).days)
    is_overdue = now_utc >= due_dt or days_elapsed >= 30

    return {
        "case_id": cid_str,
        "has_timer": True,
        "registration_no": timer.get("registration_no", ""),
        "filed_at": timer.get("filed_at", ""),
        "due_at": timer.get("due_at", ""),
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "is_overdue": is_overdue,
        "appeal_generated": bool(timer.get("appeal_generated", False)),
        "appeal_text": timer.get("appeal_text", ""),
    }


def generate_day31_appeal(
    case_id: Any,
    ground: str = "No response within the time limit",
) -> Dict[str, Any]:
    """
    Simulates Day 31 non-response escalation:
    1. Loads case and watchdog timer from SQLite.
    2. Identifies the Public Information Officer and filing details.
    3. Renders a Section 19(1) First Appeal invoking Section 7(6) (₹0 fee for delayed records).
    4. Updates database records (appeal_generated=1, appeal_text).
    """
    cid_str = str(case_id)
    case_data = db.get_case(cid_str)
    if not case_data:
        raise ValueError(f"Case with ID {cid_str} not found in database.")

    timer = case_data.get("timer")
    registration_no = timer.get("registration_no") if timer else f"RTI/2026/DEMO-{cid_str[:6]}"
    filed_date = timer.get("filed_at", "")[:10] if timer and timer.get("filed_at") else datetime.date.today().isoformat()

    # Resolve PIO name / authority
    auth_map = _load_authorities_map()
    auth_id = case_data.get("authority_id", "")
    auth_info = auth_map.get(auth_id, {})
    pio_title = auth_info.get("pio_title") or case_data.get("authority_id") or "Public Information Officer"

    # Render statutory Section 19(1) First Appeal citing Section 7(6)
    appeal_raw = rti_templates.render_first_appeal_body(
        registration_no=registration_no,
        filing_date=filed_date,
        pio_name=pio_title,
        ground=ground,
    )
    appeal_text = rti_templates.ascii_sanitize_rti_text(appeal_raw, max_chars=3000)

    # Persist appeal into timers table and update case status
    conn = db.get_connection()
    with conn:
        # If timer exists, update it; otherwise create one
        if timer:
            conn.execute(
                "UPDATE timers SET appeal_generated = 1, appeal_text = ? WHERE case_id = ?",
                (appeal_text, cid_str),
            )
        else:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            due_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
            conn.execute(
                """
                INSERT INTO timers (id, case_id, registration_no, filed_at, due_at, appeal_generated, appeal_text)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (f"TIMER-{cid_str[:8]}", cid_str, registration_no, now_iso, due_iso, appeal_text),
            )

        conn.execute(
            "UPDATE cases SET status = 'APPEAL_GENERATED' WHERE id = ?",
            (cid_str,),
        )
    conn.close()

    return {
        "case_id": cid_str,
        "registration_no": registration_no,
        "ground": ground,
        "appeal_fee": 0,
        "appeal_text": appeal_text,
        "statutory_sections": ["Section 19(1)", "Section 7(6)"],
        "status": "APPEAL_GENERATED",
    }

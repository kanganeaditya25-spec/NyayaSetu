"""
SQLite Database Layer for NyayaSetu.
Manages persistent state for Users, Cases, Legal Drafts, and 30-Day Watchdog Timers.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_FILE_PATH = Path(__file__).resolve().parent / "rti_architect.db"


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with foreign keys enabled and Row factory configured."""
    target_path = Path(db_path) if db_path else DB_FILE_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    if not salt:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    return pwd_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Securely verifies a candidate password against stored hash and salt."""
    check_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(check_hash, password_hash)


def init_db(db_path: Optional[Path | str] = None) -> None:
    """
    Initializes the SQLite schema with core tables:
    1. users - Registered citizens and authentication credentials
    2. cases - Raw complaint intake and citizen demographic profile
    3. drafts - Formatted Section 6(1) text & PDF attachments
    4. timers - 30-day statutory watchdogs and First Appeal records
    """
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                citizen_name TEXT NOT NULL,
                email TEXT NOT NULL,
                mobile TEXT,
                address TEXT,
                is_bpl INTEGER DEFAULT 0,
                raw_complaint TEXT,
                extracted_json TEXT,
                authority_id TEXT,
                status TEXT DEFAULT 'INTAKE_RECEIVED',
                created_at TEXT NOT NULL,
                user_id TEXT
            );
        """)
        # Safe migration if table existed before user_id column
        try:
            conn.execute("ALTER TABLE cases ADD COLUMN user_id TEXT;")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                draft_text TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                pdf_path TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timers (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                registration_no TEXT NOT NULL,
                filed_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                appeal_generated INTEGER DEFAULT 0,
                appeal_text TEXT,
                FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE
            );
        """)
    conn.close()


def create_user(
    full_name: str,
    email: str,
    password: str,
    user_id: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Creates a new citizen user account with hashed password credentials."""
    uid = user_id or f"USER-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pwd_hash, salt = hash_password(password)

    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO users (id, full_name, email, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uid, full_name.strip(), email.strip().lower(), pwd_hash, salt, now_iso),
        )
    conn.close()

    return {
        "id": uid,
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "created_at": now_iso,
    }


def get_user_by_email(email: str, db_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a user row by email address."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str, db_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a user profile by ID without exposing sensitive hash/salt."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user(email: str, password: str, db_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Validates citizen credentials and returns user profile if password matches."""
    user = get_user_by_email(email, db_path=db_path)
    if not user:
        return None
    if verify_password(password, user["password_hash"], user["salt"]):
        return {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "created_at": user["created_at"],
        }
    return None


def create_case(
    citizen_name: str,
    email: str,
    mobile: str = "",
    address: str = "",
    is_bpl: bool = False,
    raw_complaint: str = "",
    extracted_json: Optional[Dict[str, Any] | str] = None,
    authority_id: str = "",
    status: str = "INTAKE_RECEIVED",
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Creates a new case record and returns the inserted row as a dictionary."""
    cid = case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if extracted_json is None:
        json_str = "{}"
    elif isinstance(extracted_json, dict):
        json_str = json.dumps(extracted_json)
    else:
        json_str = str(extracted_json)

    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO cases (
                id, citizen_name, email, mobile, address, is_bpl,
                raw_complaint, extracted_json, authority_id, status, created_at, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                citizen_name.strip(),
                email.strip(),
                mobile.strip(),
                address.strip(),
                1 if is_bpl else 0,
                raw_complaint.strip(),
                json_str,
                authority_id.strip(),
                status.strip(),
                now_iso,
                user_id,
            ),
        )
    conn.close()
    return get_case(cid, db_path=db_path) or {}


def save_draft(
    case_id: str,
    draft_text: str,
    char_count: Optional[int] = None,
    pdf_path: str = "",
    draft_id: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Saves a generated legal draft associated with a case."""
    did = draft_id or f"DRAFT-{uuid.uuid4().hex[:8].upper()}"
    count = char_count if char_count is not None else len(draft_text)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO drafts (
                id, case_id, draft_text, char_count, pdf_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (did, case_id, draft_text, count, pdf_path, now_iso),
        )
    conn.close()

    return {
        "id": did,
        "case_id": case_id,
        "draft_text": draft_text,
        "char_count": count,
        "pdf_path": pdf_path,
        "created_at": now_iso,
    }


def create_timer(
    case_id: str,
    registration_no: str,
    filed_at: Optional[str] = None,
    due_at: Optional[str] = None,
    sla_days: int = 30,
    appeal_generated: bool = False,
    appeal_text: str = "",
    timer_id: Optional[str] = None,
    db_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Creates a statutory 30-day escalation timer."""
    tid = timer_id or f"TIMER-{uuid.uuid4().hex[:8].upper()}"
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    filed_iso = filed_at or now_dt.isoformat()
    if due_at:
        due_iso = due_at
    else:
        due_iso = (now_dt + datetime.timedelta(days=sla_days)).isoformat()

    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO timers (
                id, case_id, registration_no, filed_at, due_at, appeal_generated, appeal_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                case_id,
                registration_no.strip(),
                filed_iso,
                due_iso,
                1 if appeal_generated else 0,
                appeal_text,
            ),
        )
    conn.close()

    return {
        "id": tid,
        "case_id": case_id,
        "registration_no": registration_no,
        "filed_at": filed_iso,
        "due_at": due_iso,
        "appeal_generated": bool(appeal_generated),
        "appeal_text": appeal_text,
    }


def get_case(case_id: str, db_path: Optional[Path | str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single case by ID with its latest draft and timer if available."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    case_data = dict(row)
    case_data["is_bpl"] = bool(case_data.get("is_bpl"))

    # Fetch latest draft
    cursor.execute(
        "SELECT * FROM drafts WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
        (case_id,),
    )
    draft_row = cursor.fetchone()
    case_data["draft"] = dict(draft_row) if draft_row else None

    # Fetch latest timer
    cursor.execute(
        "SELECT * FROM timers WHERE case_id = ? ORDER BY filed_at DESC LIMIT 1",
        (case_id,),
    )
    timer_row = cursor.fetchone()
    case_data["timer"] = dict(timer_row) if timer_row else None

    conn.close()
    return case_data

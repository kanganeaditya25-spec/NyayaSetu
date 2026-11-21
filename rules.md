# Antigravity Workspace Rules — `RTI-Architect`

Follow these rules strictly on every task in this repository:

## 1. Tech Stack & Cost Constraints
* **Language & Runtime:** Python 3.11+ only for backend and agents.
* **Backend:** FastAPI + Uvicorn + Pydantic v2 + SQLite (`sqlite3` or SQLAlchemy).
* **Vector Store:** Local `ChromaDB` with `BAAI/bge-m3` (or `sentence-transformers/all-MiniLM-L6-v2` if low RAM).
* **Browser Automation:** `Playwright` (Chromium, `headless=False` for live demo) + optional `browser-use`.
* **100% Open-Source / Free-Tier Only:** Do NOT add OpenAI, Anthropic, or paid Google Maps/Cloud SDKs. Use local `Ollama` (`qwen2.5:7b` / `qwen2.5-vl:7b`) or free-tier OpenAI-compatible endpoints (`GROQ_API_KEY` / `HF_TOKEN`) configured via `.env`.

## 2. Statutory & Legal Safety Guardrails
* **No LLM-Invented Law:** Never let the LLM generate RTI Act section numbers or legal boilerplate from memory. All statutory citations (`Section 6(1)`, `Section 6(2)`, `Section 6(3)`, `Section 7(1)`, `Section 7(5)`, `Section 7(6)`, `Section 19(1)`) MUST be injected from deterministic templates in `backend/data/rti_templates.py`.
* **3,000-Character & Factual Rule:** `Nyaya-Draft` outputs MUST pass a deterministic Pydantic validator ensuring `len(draft_text) <= 3000` and zero `"why"` questions.
* **Consent-Gated Browser Execution:** `Setu-Browser` MUST ONLY target `http://localhost:8001/mock_portal` during development/demo and MUST hard-pause at the CAPTCHA/Payment step (`PAUSED_FOR_HUMAN_CONSENT`)—never attempt to bypass CAPTCHAs or store user passwords.

## 3. Execution & Coding Discipline
* **One Slice Per Task:** Modify ONLY the files explicitly requested in the current prompt. Do NOT refactor or rewrite previously verified files.
* **No Silent Failures:** Use explicit error messages and typed Pydantic schemas on all `/api/*` routes.
* **Verify Before Finishing:** After creating or editing any module, run a verification command (`python -m py_compile`, `pytest`, or `uvicorn` + `curl` test) and confirm zero errors before reporting completion.

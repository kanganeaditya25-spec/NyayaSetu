# `RTI-Architect` — 24-Hour Vibecoding PRD & Build Plan

**Hackathon Track:** IdeaForce Track 1 — Civic Pulse, Digital Governance & Public Information  
**Target Build Window:** 24 Hours (Solo / Small Team Vibecoding Blueprint)  
**License / Cost Profile:** 100% Open-Source Stack & Free-Tier Inference Ready  

---

## 1. Product Vision & Core Problem

Under India's [Right to Information (RTI) Act, 2005](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en), every citizen can demand government records, file notings, and status logs—without hiring a lawyer or giving a reason ([Section 6(2)](https://www.legalrepublic.in/everyday-law/templates/rti-application/)). In practice, citizen applications fail or stall for four predictable reasons:

1. **Invalid Question Framing:** Citizens ask *"Why was my scholarship/water connection delayed?"*—which Public Information Officers (PIOs) reject because the Act only covers existing records, not opinions or "why" questions ([LegalRepublic RTI Guide](https://www.legalrepublic.in/everyday-law/templates/rti-application/)).
2. **Wrong Authority Routing:** Applications sent to a central ministry instead of the field office holding the file get bounced under [Section 6(3)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en), wasting weeks.
3. **Portal & Fee Friction:** Navigating [rtionline.gov.in](https://rtionline.gov.in/guidelines.php?request) (3,000-character text limit, department dropdowns, ₹10 fee vs. BPL exemption, CAPTCHA/OTP timeouts) blocks low-literacy or regional-language citizens.
4. **Missed Escalations:** Citizens miss the 30-day statutory reply window ([Section 7(1)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en)) and fail to file a [Section 19(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) First Appeal or claim free copies under [Section 7(6)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en).

**`RTI-Architect`** solves all four by converting a citizen's regional voice note + receipt photo into a legally compliant [Section 6(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) application, co-browsing the filing portal with a human-in-the-loop safety gate, and running a 30-day escalation watchdog.

---

## 2. End-to-End Walkthrough Scenario ("Priya's 4-Month Stuck Scholarship")

1. **Messy Citizen Input:** Priya records a 25-second voice note in Hindi/Marathi (*"Mera scholarship 4 mahine se atka hai..."*) and uploads a blurry photo of her stamped district-office acknowledgment slip.
2. **Multimodal Extraction:** `Vaani-ASR` transcribes her audio; `Drishti-Doc` extracts `Application ID`, `Submission Date`, `Scheme Name`, and `Office Stamp` from the photo.
3. **Authority & SLA Mapping:** `Adhikar-RAG` identifies the exact **District Social Welfare PIO** and retrieves the department's Citizen Charter SLA.
4. **Legal Reframing:** `Nyaya-Draft` rewrites her emotional complaint into 4 crisp, factual [Section 6(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) record requests (under 3,000 characters), checks BPL status for [Section 7(5)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en) fee waiver, and reads back a 15-second plain-language summary in her language.
5. **Consent-Gated Co-Browsing:** After Priya confirms, `Setu-Browser` (Playwright) opens the RTI portal (demonstrated on a local `rtionline.gov.in` sandbox clone), selects the Public Authority, pastes the 4-point request, uploads the receipt, fills her details, and **hard-pauses** at the CAPTCHA + ₹10 UPI/NetBanking gate for human completion.
6. **30-Day Watchdog:** `Prahari-Watch` logs the Registration Number and starts a 30-day timer. On Day 31 with no reply, it auto-generates a [Section 19(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) First Appeal (₹0 fee for Central authorities) invoking [Section 7(6)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en) for free document copies.

---

## 3. Statutory Law & Guardrail Matrix (Deterministic Rules)

Never let an LLM hallucinate legal sections. Enforce these exact [RTI Act, 2005](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en) rules via deterministic Python templates and validators:

| Legal Provision | Rule & Operational Effect | Code Guardrail in `RTI-Architect` |
| :--- | :--- | :--- |
| **Section 6(1)** | Written request in English, Hindi, or official regional language asking for existing records/file notings ([LegalRepublic](https://www.legalrepublic.in/everyday-law/templates/rti-application/)). | Regex + LLM critic blocks *"why"* / speculative questions; enforces numbered record requests. |
| **Section 6(2)** | Applicant cannot be forced to give a reason for seeking information ([LegalRepublic](https://www.legalrepublic.in/everyday-law/templates/rti-application/)). | Strips unnecessary personal backstory from the final legal body; keeps under 3,000 chars ([RTI Online](https://rtionline.gov.in/guidelines.php?request)). |
| **Section 6(3)** | If sent to wrong authority, must be transferred within 5 days ([Vikaspedia](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en)). | `Adhikar-RAG` targets the record-holding field office first to avoid transfer delays. |
| **Section 7(1)** | PIO must reply within **30 days** (or **48 hours** if life/liberty is involved) ([Vikaspedia](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en)). | `Prahari-Watch` sets a 30-day (or 48-hour urgency flag) countdown from submission timestamp. |
| **Section 7(5)** | Below Poverty Line (BPL) applicants pay **₹0** application fee upon attaching BPL proof ([Vikaspedia](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en)). | Toggle `is_bpl=True` injects Section 7(5) exemption text and prompts BPL card attachment. |
| **Section 7(6)** | If PIO fails to reply within time limit, information must be provided **free of charge** ([Vikaspedia](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en)). | Automatically appended to First Appeal when `days_elapsed > 30`. |
| **Section 19(1)** | First Appeal to First Appellate Authority within 30 days of non-reply/refusal; **₹0 fee** for Central authorities ([Vikaspedia](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en)). | 1-click Appeal PDF & portal-fill workflow triggered in `Prahari-Watch`. |

---

## 4. Multi-Agent AI Architecture (100% Open-Source Stack)

| Agent Name | Role | Input → Output | Open-Source Model / Tooling | Fallback (Low-VRAM Laptop) |
| :--- | :--- | :--- | :--- | :--- |
| **`Vaani-ASR`** | Regional Voice Intake & Summary Readback | `.wav/.ogg` audio → Clean text + TTS audio | [AI4Bharat IndicConformer](https://github.com/AI4Bharat/IndicConformerASR) (22 languages) + [Indic-TTS](https://github.com/AI4Bharat/Indic-TTS) | Quantized `faster-whisper-small` + browser Web Speech API |
| **`Drishti-Doc`** | Receipt & Stamp Extractor | Blurry JPG/PNG → Structured JSON (`app_id`, `date`, `office`, `scheme`) | `Qwen2.5-VL-7B` (via Ollama/HF) or `PaddleOCR` + OpenCV | `PaddleOCR` text + `Qwen2.5-7B` JSON parser |
| **`Adhikar-RAG`** | PIO & Citizen Charter Mapper | Extracted `office` + `scheme` → Exact Public Authority, PIO title, SLA days | `BAAI/bge-m3` embeddings + `ChromaDB` (local) | SQLite FTS5 + curated JSON directory of 25 authorities |
| **`Nyaya-Draft`** | Complaint-to-Section 6(1) Rewriter | Citizen complaint + JSON context → 4 numbered record requests (`<=3000` chars) | `Qwen2.5-7B-Instruct` or `Llama-3.1-8B-Instruct` (Ollama / Groq free tier) | Same model via Hugging Face Inference API |
| **`Setu-Browser`** | Consent-Gated Portal Co-Pilot | Draft JSON + attachment → Filled portal form paused at CAPTCHA/Payment | [browser-use](https://github.com/browser-use/browser-use) + **Playwright** (against local portal clone) | Deterministic Playwright script with explicit `page.pause()` gate |
| **`Prahari-Watch`** | 30-Day Escalation Watchdog | Registration ID + filing date → Countdown + Section 19(1) Appeal PDF | Python `APScheduler` + `SQLite` + `WeasyPrint`/Jinja2 PDF | Manual "Simulate Day 31" button for live demo |

---

## 5. System & Data Architecture

### Project Directory Layout (Vibecoding Ready)
```text
rti-architect/
├── backend/
│   ├── main.py                  # FastAPI entrypoint
│   ├── agents/
│   │   ├── vaani_asr.py         # Audio transcription & TTS
│   │   ├── drishti_doc.py       # OCR / VLM receipt parser
│   │   ├── adhikar_rag.py       # ChromaDB PIO & SLA lookup
│   │   ├── nyaya_draft.py       # Section 6(1) rewriter + 3000-char validator
│   │   ├── setu_browser.py      # Playwright / browser-use co-pilot
│   │   └── prahari_watch.py     # Day-31 escalation & Appeal generator
│   ├── data/
│   │   ├── authorities.json     # Seeded 25 Central/State PIOs & SLAs
│   │   └── rti_templates.py     # Verified Section 6(1), 7(5), 7(6), 19(1) templates
│   └── db.py                    # SQLite models (cases, drafts, timers)
├── mock_portal/
│   └── index.html               # Local clone of rtionline.gov.in form + CAPTCHA gate
├── frontend/                    # Next.js / React + Tailwind UI
└── README.md
```

### Core API Endpoints
* `POST /api/intake` — Accepts audio blob + receipt image + `is_bpl` flag; runs `Vaani-ASR` -> `Drishti-Doc` -> `Adhikar-RAG` -> `Nyaya-Draft`; returns JSON diff (`raw_complaint` vs. `statutory_questions`, `pio_target`, `char_count`, `audio_summary_url`).
* `POST /api/execute-browser` — Launches `Setu-Browser` against `http://localhost:8001/mock_portal`, fills all fields, attaches receipt, pauses at CAPTCHA/Payment, and returns `registration_number` upon user completion.
* `POST /api/cases/{id}/simulate-day31` — Triggers `Prahari-Watch` to generate a downloadable Section 19(1) First Appeal invoking Section 7(6) free-copy penalty.

---

## 6. 24-Hour Vibecoding Execution Plan

### Hours 0–4: Foundation, Mock Portal & Seed Data
* **Goal:** Lock the environment, SQLite schema, `authorities.json` (25 real department/PIO entries), and the local `mock_portal/index.html` mimicking [rtionline.gov.in](https://rtionline.gov.in/guidelines.php?request) (Ministry dropdown, 3,000-char textarea, file upload, CAPTCHA box, ₹10/BPL toggle).
* **Vibecoding Prompt Tip:** Build `mock_portal/index.html` and `rti_templates.py` first so every downstream agent has a deterministic target.

### Hours 4–10: Core AI Pipeline (`Vaani-ASR`, `Drishti-Doc`, `Adhikar-RAG`, `Nyaya-Draft`)
* **Goal:** Wire FastAPI `/api/intake` end-to-end.
* **Checkpoints:**
  * Test `Drishti-Doc` on 3 sample receipt images (clean, tilted, blurry).
  * Enforce strict Pydantic output on `Nyaya-Draft` so zero *"why"* questions pass through and `len(draft_text) <= 3000`.

### Hours 10–16: `Setu-Browser` (Playwright Co-Pilot) & `Prahari-Watch`
* **Goal:** Connect Playwright (+ optional `browser-use` fallback) to `/api/execute-browser` so clicking **"Auto-Fill RTI Portal"** opens Chromium, fills the mock portal live on screen, and highlights the CAPTCHA/Payment box with a **"Waiting for Citizen Consent"** banner.
* **Checkpoints:** Build `Prahari-Watch` with a **"Simulate Day 31 (No Reply)"** button that renders the Section 19(1) First Appeal.

### Hours 16–20: Frontend UI (Citizen-First + Judge-Friendly Diff View)
* **Goal:** Clean 3-screen mobile-responsive UI:
  1. **Voice + Receipt Upload Screen** (with BPL toggle & Life/Liberty urgency toggle).
  2. **Side-by-Side Legal Diff Screen** (*"What You Said"* vs. *"What `RTI-Architect` Drafted"* + Audio Readback).
  3. **Live Co-Browser & 30-Day Tracker Dashboard** (Registration ID, countdown badge, 1-click First Appeal).

### Hours 20–24: End-to-End Rehearsal, Edge Cases & Pitch Prep
* **Goal:** Record a 60-second backup video of the live Playwright run (in case venue Wi-Fi drops), pre-cache 2 sample voice clips + receipt images, and rehearse the 3-minute demo script.

---

## 7. 3-Minute IdeaForce Demo Script & Judge Q&A Defense

### Demo Flow
* **0:00–0:45 (Problem & Intake):** Upload a blurry scholarship receipt + play a 15s Hindi/Marathi voice rant. Explain why normal chatbots fail citizens at the filing stage.
* **0:45–1:40 (Legal Intelligence):** Show the side-by-side diff—raw complaint transformed into 4 surgical [Section 6(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) record requests, mapped to the exact District PIO, with [Section 7(5)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en) BPL fee exemption applied.
* **1:40–2:35 (Live Co-Browsing):** Click **Launch Co-Pilot**. Watch Playwright fill the local RTI portal clone in real time and pause safely at the CAPTCHA/Payment gate.
* **2:35–3:00 (Accountability Loop):** Click **Simulate Day 31** to generate the [Section 19(1)](https://www.legalrepublic.in/everyday-law/templates/rti-application/) First Appeal citing [Section 7(6)](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/rti-fees-and-payment-modes?lgn=en).

### Likely Judge Questions (Ready Answers)
* *"Isn't automating government portals against terms of service / risky?"* → **Answer:** That is why `Setu-Browser` is a **consent-gated co-pilot**, not an unattended bot. It never bypasses CAPTCHAs, never stores citizen passwords, and requires explicit human review and payment confirmation.
* *"What if the LLM hallucinates a law section?"* → **Answer:** The LLM never writes statutory citations—it only outputs factual bullet points injected into verified, static [RTI Act 2005](https://egovernance.vikaspedia.in/viewcontent/e-governance/about-rti-act-2005/how-to-file-an-rti-application-online-and-offline?lgn=en) templates.

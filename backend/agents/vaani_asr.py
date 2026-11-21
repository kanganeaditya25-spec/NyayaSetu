"""
Vaani-ASR: Voice Intake Transcription & Plain-Language Summary Agent.
Transcribes regional citizen audio notes using Groq's whisper-large-v3-turbo,
and generates reassuring 2-sentence plain-language summaries for TTS readback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from backend.agents import llm_client

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
WHISPER_MODEL = "whisper-large-v3-turbo"

# Explicit ISO 639-1 language code mapping so regional Indian languages
# (especially Hindi and Marathi) are not misclassified as Urdu or other languages.
LANGUAGE_MAP: Dict[str, str] = {
    "Hindi": "hi",
    "hindi": "hi",
    "hi": "hi",
    "Marathi": "mr",
    "marathi": "mr",
    "mr": "mr",
    "English": "en",
    "english": "en",
    "en": "en",
    "Gujarati": "gu",
    "gujarati": "gu",
    "Punjabi": "pa",
    "punjabi": "pa",
    "Tamil": "ta",
    "tamil": "ta",
    "Telugu": "te",
    "telugu": "te",
    "Bengali": "bn",
    "bengali": "bn",
    "Kannada": "kn",
    "kannada": "kn",
}


def transcribe_audio(
    audio_path: str,
    language_hint: Optional[str] = None,
) -> Dict[str, str]:
    """
    Sends an audio file (.wav, .mp3, .m4a, .ogg) to Groq's Whisper API endpoint
    using whisper-large-v3-turbo (supports Hindi, Marathi, English, and Indian languages).
    Maps language_hint through LANGUAGE_MAP to ensure correct ISO language code.
    Returns a dictionary with 'transcript' and 'language'.
    """
    file_path = Path(audio_path)
    if not file_path.exists():
        return {
            "transcript": "",
            "language": language_hint or "en",
            "error": f"Audio file not found at {audio_path}",
        }

    groq_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
    if not groq_key:
        return {
            "transcript": "",
            "language": language_hint or "en",
            "error": "GROQ_API_KEY not configured",
        }

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {groq_key}"}

    data: Dict[str, Any] = {
        "model": WHISPER_MODEL,
        "response_format": "json",
    }
    if language_hint:
        mapped_lang = LANGUAGE_MAP.get(language_hint, language_hint)
        data["language"] = mapped_lang

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, headers=headers, data=data, files=files)
                resp.raise_for_status()
                res_data = resp.json()
                transcript = res_data.get("text", "").strip()
                detected_lang = res_data.get("language") or (LANGUAGE_MAP.get(language_hint, language_hint) if language_hint else "en")
                return {
                    "transcript": transcript,
                    "language": detected_lang,
                }
    except Exception as e:
        return {
            "transcript": "",
            "language": language_hint or "en",
            "error": f"Audio transcription failed: {str(e)}",
        }


def build_citizen_summary(
    draft_questions: List[str],
    authority_name: str,
    is_bpl: bool,
    target_language: str = "English",
) -> str:
    """
    Uses LLM to synthesize a concise, reassuring 2-sentence plain-language summary
    suitable for audio TTS readback, explaining the destination Public Authority
    and the applicable fee structure (₹0 BPL fee waiver vs ₹10 standard).
    """
    fee_desc = "Below Poverty Line (Fee: Rs. 0 Exemption under Section 7(5))" if is_bpl else "Standard Fee: Rs. 10"
    questions_summary = "; ".join(draft_questions[:3]) if draft_questions else "requesting certified file records"

    system_prompt = (
        "You are Vaani, a compassionate civic legal assistant for Indian citizens.\n"
        f"Your task is to generate a concise, reassuring 2-sentence plain-language summary in {target_language}.\n"
        "The summary will be read aloud via Text-to-Speech (TTS) to the citizen.\n"
        "Sentence 1: State clearly which government office the RTI application is being submitted to and what records are requested.\n"
        "Sentence 2: Explain the fee rule (Section 7(5) BPL free exemption of Rs. 0, or standard Rs. 10 fee).\n"
        "Format: Return ONLY a JSON object: {\"summary\": \"your 2-sentence summary\"}"
    )

    user_prompt = (
        f"Public Authority: {authority_name}\n"
        f"Key Questions: {questions_summary}\n"
        f"Fee Status: {fee_desc}\n"
        f"Target Language: {target_language}\n\n"
        f"Generate the reassuring 2-sentence TTS summary in {target_language}."
    )

    resp = llm_client.chat_json(system_prompt, user_prompt)
    summary_text = resp.get("summary")

    if summary_text and isinstance(summary_text, str) and summary_text.strip():
        return summary_text.strip()

    # Deterministic fallback by target language
    lang_lower = target_language.lower()
    if "hindi" in lang_lower or "hi" in lang_lower:
        fee_phrase = (
            "बीपीएल छूट के तहत धारा 7(5) के अनुसार आवेदन शुल्क शून्य रुपये (₹0) है।"
            if is_bpl
            else "आवेदन शुल्क केवल 10 रुपये (₹10) है।"
        )
        return f"आपकी आरटीआई अर्जी {authority_name} को भेजी जा रही है ताकि आपके आवश्यक रिकॉर्ड मिल सकें। {fee_phrase}"
    elif "marathi" in lang_lower or "mr" in lang_lower:
        fee_phrase = (
            "दारिद्र्यरेषेखालील (BPL) सवलतीनुसार कलम 7(5) अंतर्गत अर्ज शुल्क शून्य रुपये (₹0) आहे."
            if is_bpl
            else "नियमित अर्ज शुल्क फक्त 10 रुपये (₹10) आहे."
        )
        return f"तुमचा आरटीआय अर्ज {authority_name} कडे आवश्यक नोंदी मिळवण्यासाठी पाठवला जात आहे. {fee_phrase}"
    else:
        fee_phrase = (
            "Under Section 7(5), the application fee is completely waived (Rs. 0) for Below Poverty Line (BPL) applicants."
            if is_bpl
            else "The prescribed application fee is Rs. 10."
        )
        return f"Your RTI application is being prepared for submission to {authority_name} to obtain certified records. {fee_phrase}"

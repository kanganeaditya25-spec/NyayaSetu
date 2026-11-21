"""
OpenAI-Compatible LLM Client for RTI-Architect.
Supports free-tier Groq and local Ollama inference via httpx with clean JSON output parsing.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv

# Load environment configuration from project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()


def extract_json_from_response(raw_text: str) -> Dict[str, Any]:
    """
    Cleans markdown code fences and extracts a valid JSON dictionary from LLM output.
    """
    if not raw_text or not raw_text.strip():
        return {}

    text = raw_text.strip()

    # Strip markdown code blocks like ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Try direct parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}
    except json.JSONDecodeError:
        pass

    # Fallback: regex search for the first JSON object {...}
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {"error": "Failed to parse JSON from LLM response", "raw": raw_text}


GROQ_FALLBACK_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

def chat_json(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Sends a chat completion request to the configured LLM provider (Groq or Ollama)
    and returns a structured JSON dictionary.
    """
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER).lower().strip()
    target_model = model or os.getenv("LLM_MODEL", LLM_MODEL)
    groq_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
    ollama_url = os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL).rstrip("/")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    models_to_try = [target_model]
    if provider == "groq":
        for fm in GROQ_FALLBACK_MODELS:
            if fm not in models_to_try:
                models_to_try.append(fm)

    last_error = ""
    for current_model in models_to_try:
        if provider == "groq":
            endpoint = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": current_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 1024,
            }
        else:  # Default to local Ollama
            endpoint = f"{ollama_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": current_model,
                "messages": messages,
                "format": "json",
                "temperature": 0.1,
                "stream": False,
            }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                if resp.status_code == 404 and "model_not_found" in resp.text and provider == "groq":
                    last_error = resp.text
                    continue  # Try next available Groq model
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return extract_json_from_response(content)

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            last_error = f"LLM HTTP Error {status}: {e.response.text}"
            if status == 404 and provider == "groq":
                continue
            break
        except Exception as e:
            last_error = f"LLM Request Failed: {str(e)}"
            break

    return {
        "error": last_error,
        "fallback_used": True,
    }

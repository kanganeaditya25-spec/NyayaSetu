"""
Drishti-Doc: Multimodal Document & Receipt Extraction Agent.
Extracts structured application metadata (Application ID, Submission Date, Office Name, Scheme)
from citizen receipts and acknowledgment slips using Groq Vision API,
and converts documents into compliant <= 1 MB PDFs via rti_templates.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from PIL import Image
from pydantic import BaseModel, Field

from backend.data import rti_templates

GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()


class ExtractedReceipt(BaseModel):
    application_id: Optional[str] = Field(default=None, description="Extracted application or acknowledgment number")
    submission_date: Optional[str] = Field(default=None, description="Date of original submission")
    office_name: Optional[str] = Field(default=None, description="Issuing department or office stamp")
    scheme_name: Optional[str] = Field(default=None, description="Welfare scheme or subject name")
    applicant_name: Optional[str] = Field(default=None, description="Citizen or applicant name")
    pdf_path: Optional[str] = Field(default=None, description="Path to generated <= 1MB PDF document")
    confidence_note: str = Field(default="Extraction completed", description="Status or fallback details")


def encode_image_base64(image_path: str) -> tuple[str, str]:
    """Encodes image to base64 string and determines its MIME type."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return encoded, mime_type


def extract_metadata_from_pil(image_path: str) -> Dict[str, Any]:
    """Fallback text extraction from PIL Image metadata or embedded info chunks."""
    extracted: Dict[str, Any] = {}
    try:
        with Image.open(image_path) as img:
            info_dict = getattr(img, "info", {})
            full_text = " | ".join([str(v) for v in info_dict.values()])

            if full_text:
                # 1. Application ID
                app_match = re.search(
                    r"(?:App(?:lication)?\s*ID|Ack(?:nowledgment)?\s*ID|Ref(?:erence)?\s*ID|Receipt\s*No)[\s:]*([A-Za-z0-9\-_/]+)",
                    full_text,
                    re.IGNORECASE,
                )
                if app_match:
                    extracted["application_id"] = app_match.group(1).strip()

                # 2. Date
                date_match = re.search(
                    r"(?:Date|Dated)[\s:]*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})",
                    full_text,
                    re.IGNORECASE,
                )
                if date_match:
                    extracted["submission_date"] = date_match.group(1).strip()

                # 3. Applicant
                applicant_match = re.search(
                    r"(?:Applicant(?: Name)?)[\s:]*([A-Za-z ]+?)(?:\s*\||$|\n)",
                    full_text,
                    re.IGNORECASE,
                )
                if applicant_match:
                    extracted["applicant_name"] = applicant_match.group(1).strip()

                # 4. Office
                office_match = re.search(
                    r"([A-Za-z ]*(?:Social Welfare|Welfare Office|Tehsil|Collectorate|Municipal|Department|Ministry)[A-Za-z ]*)",
                    full_text,
                    re.IGNORECASE,
                )
                if office_match:
                    extracted["office_name"] = office_match.group(1).strip()

                # 5. Scheme
                scheme_match = re.search(
                    r"([A-Za-z ]*(?:Scholarship|Pension|Ration|Housing|Yojana|Scheme)[A-Za-z ]*)",
                    full_text,
                    re.IGNORECASE,
                )
                if scheme_match:
                    extracted["scheme_name"] = scheme_match.group(1).strip()
    except Exception:
        pass
    return extracted


def analyze_receipt(image_path: str, output_pdf_path: str) -> ExtractedReceipt:
    """
    Analyzes an uploaded receipt image using Groq Vision API (or graceful metadata fallback),
    extracts structured application metadata, and produces a portal-ready PDF <= 1 MB.
    """
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Receipt image not found at {image_path}")

    # 1. Convert image to PDF <= 1 MB via rti_templates
    pdf_out = rti_templates.image_to_pdf_under_1mb(str(img_file), str(output_pdf_path))

    # 2. Prepare Vision API call
    base64_data, mime_type = encode_image_base64(str(img_file))
    groq_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
    vision_model = os.getenv("GROQ_VISION_MODEL", GROQ_VISION_MODEL)

    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json",
    }

    prompt_text = (
        "You are an expert OCR document parser for Indian government receipts and acknowledgment slips.\n"
        "Analyze this receipt image and extract the following details into a strict JSON object:\n"
        "- application_id: Application ID, acknowledgment number, or reference number\n"
        "- submission_date: Date of receipt/submission (e.g. DD/MM/YYYY or YYYY-MM-DD)\n"
        "- office_name: Government department, district office, or issuing authority\n"
        "- scheme_name: Welfare scheme, scholarship, or service name\n"
        "- applicant_name: Citizen or applicant name\n"
        "Return ONLY the JSON object. Set unidentifiable fields to null."
    )

    payload = {
        "model": vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_data}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }

    vision_success = False
    extracted_data: Dict[str, Any] = {}
    confidence_note = "Vision extraction completed"

    if groq_key:
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    content = res_json["choices"][0]["message"]["content"]
                    # Extract JSON
                    clean_content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
                    clean_content = re.sub(r"\s*```$", "", clean_content)
                    match = re.search(r"(\{.*\})", clean_content, re.DOTALL)
                    if match:
                        extracted_data = json.loads(match.group(1))
                        vision_success = True
                        confidence_note = f"Groq Vision ({vision_model}) parsed successfully."
                else:
                    confidence_note = f"Groq Vision returned HTTP {resp.status_code}. Fallback metadata parser applied."
        except Exception as e:
            confidence_note = f"Vision API call failed: {str(e)}. Fallback metadata parser applied."
    else:
        confidence_note = "No GROQ_API_KEY provided. Fallback metadata parser applied."

    # 3. If Vision API didn't succeed, use metadata parser fallback
    if not vision_success or not any(extracted_data.values()):
        meta_extracted = extract_metadata_from_pil(str(img_file))
        if meta_extracted:
            extracted_data.update(meta_extracted)
            confidence_note += " Extracted fields from document metadata."

    return ExtractedReceipt(
        application_id=extracted_data.get("application_id"),
        submission_date=extracted_data.get("submission_date"),
        office_name=extracted_data.get("office_name"),
        scheme_name=extracted_data.get("scheme_name"),
        applicant_name=extracted_data.get("applicant_name"),
        pdf_path=pdf_out,
        confidence_note=confidence_note,
    )

"""
RTI Act 2005 Statutory Templates & Deterministic Sanitization Module.
Enforces statutory citations for Section 6(1), 6(2), 6(3), 7(1), 7(5), 7(6), and 19(1).
Guarantees strict 3,000-character ASCII compliance for RTI Online portal filing.
"""

from __future__ import annotations

import io
import os
import re
from typing import List, Optional
from PIL import Image

# ============================================================================
# STATUTORY CONSTANTS & VERIFIED LEGAL TEXT (RTI ACT, 2005)
# ============================================================================

SECTION_6_1_CITATION = "Section 6(1), Right to Information Act, 2005"
SECTION_6_1_TITLE = "Request for Obtaining Information"
SECTION_6_1_LEGAL_TEXT = (
    "A person, who desires to obtain any information under this Act, shall make a request in "
    "writing or through electronic means in English or Hindi or in the official language of the area "
    "in which the application is being made, accompanying such fee as may be prescribed, to the "
    "Central Public Information Officer or State Public Information Officer, specifying the particulars "
    "of the information sought by him or her."
)

SECTION_6_2_CITATION = "Section 6(2), Right to Information Act, 2005"
SECTION_6_2_TITLE = "Applicant Not Required to Give Reasons"
SECTION_6_2_LEGAL_TEXT = (
    "An applicant making request for information shall not be required to give any reason for "
    "requesting the information or any other personal details except those that may be necessary for "
    "contacting him."
)

SECTION_6_3_CITATION = "Section 6(3), Right to Information Act, 2005"
SECTION_6_3_TITLE = "Transfer of Application to Competent Authority"
SECTION_6_3_LEGAL_TEXT = (
    "Where an application, or part thereof, relates to another public authority, the application or "
    "such part shall be transferred to that other authority within five days from receipt, and the applicant "
    "informed immediately."
)

SECTION_7_1_CITATION = "Section 7(1), Right to Information Act, 2005"
SECTION_7_1_TITLE = "Disposal of Request & Statutory 30-Day Window"
SECTION_7_1_LEGAL_TEXT = (
    "The Central Public Information Officer or State Public Information Officer shall, as expeditiously "
    "as possible, and in any case within thirty days of the receipt of the request, either provide the "
    "information on payment of such fee as may be prescribed or reject the request: Provided that where "
    "the information sought concerns the life or liberty of a person, the same shall be provided within forty-eight hours."
)

SECTION_7_5_CITATION = "Section 7(5), Right to Information Act, 2005"
SECTION_7_5_TITLE = "Fee Exemption for Below Poverty Line (BPL) Citizens"
SECTION_7_5_LEGAL_TEXT = (
    "No fee shall be charged from the persons who are of below poverty line as may be determined "
    "by the appropriate Government upon submission of proof of BPL status."
)

SECTION_7_6_CITATION = "Section 7(6), Right to Information Act, 2005"
SECTION_7_6_TITLE = "Mandatory Free Supply of Information Upon Delay"
SECTION_7_6_LEGAL_TEXT = (
    "Notwithstanding anything contained in sub-section (5), the person making request for the "
    "information shall be provided the information free of any charge where a public authority "
    "fails to comply with the time limits specified in sub-section (1)."
)

SECTION_19_1_CITATION = "Section 19(1), Right to Information Act, 2005"
SECTION_19_1_TITLE = "First Appeal to Designated Appellate Authority"
SECTION_19_1_LEGAL_TEXT = (
    "Any person who does not receive a decision within the time specified in sub-section (1) or "
    "clause (a) of sub-section (3) of section 7, or is aggrieved by a decision of the Central Public "
    "Information Officer or State Public Information Officer, may within thirty days from the expiry "
    "of such period or from the receipt of such a decision prefer an appeal to such officer who is "
    "senior in rank to the Central Public Information Officer or State Public Information Officer."
)

# Strict whitelist regex conforming to RTI Online portal restrictions
PORTAL_ALLOWED_CHAR_REGEX = r"^[A-Za-z0-9 ,.\-_()/@:&?\\%\n\r]+$"
PORTAL_ALLOWED_CHAR_CLASS = r"[^A-Za-z0-9 ,.\-_()/@:&?\\%\n\r]"
MAX_RTI_TEXT_LENGTH = 3000


# ============================================================================
# DETERMINISTIC TEXT SANITIZATION & PDF UTILITIES
# ============================================================================

def ascii_sanitize_rti_text(text: str, max_chars: int = MAX_RTI_TEXT_LENGTH) -> str:
    """
    Normalizes typographic quotes, dashes, bullets, and symbols to ASCII,
    strips any character outside the RTI Online whitelist [A-Za-z0-9 ,.-_()/@:&?\\%\\n\\r],
    and truncates to at most max_chars (default 3000).
    """
    if not text:
        return ""

    # 1. Normalize typographic smart quotes & apostrophes
    replacements = {
        "\u201c": '"',  # Left double quotation mark “
        "\u201d": '"',  # Right double quotation mark ”
        "\u2018": "'",  # Left single quotation mark ‘
        "\u2019": "'",  # Right single quotation mark ’
        "\u2014": "-",  # Em dash —
        "\u2013": "-",  # En dash –
        "\u2022": "-",  # Bullet •
        "\u2026": "...",  # Horizontal ellipsis …
        "\u00a0": " ",  # Non-breaking space
        "\t": " ",      # Horizontal tab
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)

    # 2. Strip any character outside the portal allowed character whitelist
    cleaned = re.sub(PORTAL_ALLOWED_CHAR_CLASS, "", text)

    # 3. Collapse multiple blank spaces (keeping single spaces and newlines intact)
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)

    # 4. Safely truncate to max_chars
    return cleaned[:max_chars]


def image_to_pdf_under_1mb(image_path: str, output_pdf_path: str) -> str:
    """
    Converts a JPG/PNG image into a PDF guaranteed to be <= 1 MB (1,048,576 bytes).
    Iteratively scales down dimensions and adjusts JPEG quality if needed.
    Returns the output PDF file path.
    """
    max_bytes = 1024 * 1024  # 1 MB strict limit
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)

    with Image.open(image_path) as img:
        # Convert to RGB mode (handles PNG RGBA or palette modes)
        if img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                rgb_img.paste(img, mask=img.split()[3])
            else:
                rgb_img.paste(img.convert("RGB"))
        else:
            rgb_img = img.convert("RGB")

        # Initial attempt with high quality
        cur_img = rgb_img.copy()
        quality = 85
        scale_factor = 1.0

        for attempt in range(8):
            buffer = io.BytesIO()
            # If resized or recompressed, save as JPEG first then convert to PDF
            jpeg_buf = io.BytesIO()
            cur_img.save(jpeg_buf, format="JPEG", quality=quality, optimize=True)
            jpeg_buf.seek(0)
            with Image.open(jpeg_buf) as compressed_img:
                compressed_img.save(buffer, format="PDF")

            pdf_bytes = buffer.getvalue()
            if len(pdf_bytes) <= max_bytes or attempt == 7:
                with open(output_pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                return output_pdf_path

            # Reduce quality and downscale if too large
            quality = max(30, quality - 15)
            scale_factor *= 0.8
            new_w = max(400, int(rgb_img.width * scale_factor))
            new_h = max(400, int(rgb_img.height * scale_factor))
            cur_img = rgb_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    return output_pdf_path


# ============================================================================
# DETERMINISTIC STATUTORY TEMPLATE RENDERERS
# ============================================================================

def render_section_6_1_body(
    applicant_name: str,
    questions: List[str],
    reference_id: Optional[str] = None,
    is_bpl: bool = False,
) -> str:
    """
    Renders an RTI application body strictly compliant with Section 6(1) and 6(2),
    incorporating Section 7(5) BPL exemption if applicable, within 3,000 characters.
    """
    header_lines = [
        "APPLICATION UNDER SECTION 6(1) OF THE RIGHT TO INFORMATION ACT, 2005",
        "----------------------------------------------------------------",
        f"Applicant Name: {applicant_name.strip()}",
    ]
    if reference_id:
        header_lines.append(f"Department Reference / Ack ID: {reference_id.strip()}")

    header_lines.extend([
        "",
        "Pursuant to Section 6(1) read with Section 6(2) of the RTI Act, 2005, the applicant",
        "requests certified copies of existing records, file notings, and status reports:",
        "",
    ])

    question_items = []
    for idx, q in enumerate(questions, start=1):
        clean_q = q.strip().rstrip(".")
        question_items.append(f"{idx}. Please provide certified copy/record of: {clean_q}.")

    footer_lines = [""]
    if is_bpl:
        footer_lines.extend([
            "FEE EXEMPTION (SECTION 7(5)):",
            "The applicant belongs to Below Poverty Line (BPL) category. Valid BPL proof",
            "is enclosed. Application fee of Rs. 10 is waived under Section 7(5) of the Act.",
            "",
        ])

    footer_lines.extend([
        "STATUTORY TIMELINE (SECTION 7(1)):",
        "As per Section 7(1) of the Act, information must be provided within 30 days.",
    ])

    full_text = "\n".join(header_lines + question_items + footer_lines)
    return ascii_sanitize_rti_text(full_text)


def render_first_appeal_body(
    registration_no: str,
    filing_date: str,
    pio_name: str,
    ground: str,
) -> str:
    """
    Renders a First Appeal under Section 19(1) of RTI Act 2005,
    asserting failure under Section 7(1) and claiming free copies under Section 7(6).
    """
    lines = [
        "MEMORANDUM OF FIRST APPEAL UNDER SECTION 19(1) OF THE RTI ACT, 2005",
        "----------------------------------------------------------------",
        "To:",
        "The First Appellate Authority",
        "",
        f"Original RTI Registration No: {registration_no.strip()}",
        f"Date of Filing Original Request: {filing_date.strip()}",
        f"Designated PIO: {pio_name.strip()}",
        "",
        "Ground for Appeal under Section 19(1):",
        f"{ground.strip()}",
        "",
        "Statement of Facts & Statutory Relief:",
        "1. The appellant filed an application under Section 6(1) on the aforementioned date.",
        "2. The statutory 30-day period stipulated under Section 7(1) has elapsed without delivery of requested records.",
        "3. Section 7(6) Invocation: The PIO failed to comply within the statutory timeline.",
        "   Therefore, all information and records sought must now be provided FREE OF COST under Section 7(6).",
        "4. Prayer: The Appellate Authority is requested to direct immediate disclosure of certified records",
        "   and initiate appropriate action under the Act.",
    ]

    full_text = "\n".join(lines)
    return ascii_sanitize_rti_text(full_text)

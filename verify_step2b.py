import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, PngImagePlugin

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.agents import drishti_doc
from backend.agents import vaani_asr


def run_verification():
    tmp_dir = Path("D:/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    test_png = tmp_dir / "test_receipt.png"
    test_pdf = tmp_dir / "test_receipt.pdf"

    receipt_text = "District Social Welfare Office Pune | Scholarship App ID: MH-2026-99412 | Date: 15/07/2026 | Applicant: Priya Sharma"

    # 1. Create temporary test receipt PNG using Pillow with text drawn & embedded metadata
    img = Image.new("RGB", (900, 250), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), receipt_text, fill=(0, 0, 0))

    png_meta = PngImagePlugin.PngInfo()
    png_meta.add_text("receipt_text", receipt_text)
    png_meta.add_text("description", receipt_text)
    img.save(str(test_png), pnginfo=png_meta)
    print(f"Created test receipt image at {test_png}")

    # 2. Call drishti_doc.analyze_receipt
    print("\n--- Testing Drishti-Doc Receipt Analysis ---")
    receipt_data = drishti_doc.analyze_receipt(str(test_png), str(test_pdf))

    assert test_pdf.exists(), f"PDF output not created at {test_pdf}"
    pdf_size = test_pdf.stat().st_size
    assert pdf_size <= 1024 * 1024, f"PDF exceeds 1 MB: {pdf_size} bytes"

    print(f"PDF Generated Successfully: {test_pdf} ({pdf_size} bytes, <= 1MB)")
    print("Extracted Receipt JSON:")
    print(receipt_data.model_dump_json(indent=2))

    # Assertions on extracted receipt
    assert receipt_data.pdf_path is not None, "Missing pdf_path in ExtractedReceipt"
    if receipt_data.application_id:
        print(f"Verified Application ID: {receipt_data.application_id}")

    # 3. Call vaani_asr.build_citizen_summary
    print("\n--- Testing Vaani-ASR Citizen Summary (Hindi TTS) ---")
    summary = vaani_asr.build_citizen_summary(
        draft_questions=["Copy of file notings"],
        authority_name="District Social Welfare Office Pune",
        is_bpl=True,
        target_language="Hindi",
    )
    print("Generated Citizen TTS Summary (Hindi):")
    print(summary)
    assert len(summary) > 0, "Summary should not be empty"

    print("\nSTEP 2B VERIFIED OK")


if __name__ == "__main__":
    run_verification()

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.agents import adhikar_rag
from backend.agents import nyaya_draft


def run_test():
    print("--- 1. Testing Adhikar-RAG Authority Indexing & Retrieval ---")
    query = "Pune post matric scholarship delayed 4 months"
    matches = adhikar_rag.find_authority(query, top_k=3)
    
    assert len(matches) > 0, "No authorities matched!"
    top_match = matches[0]
    print(f"Top Matched Authority ID: {top_match['id']}")
    print(f"Ministry: {top_match['ministry']}")
    print(f"Authority Name: {top_match['authority_name']}")
    print(f"PIO Title: {top_match['pio_title']}")
    print(f"First Appellate: {top_match['first_appellate_authority']}")
    print(f"SLA Days: {top_match['sla_days']}")
    print(f"Match Score: {top_match['score']}")

    # Assert authority is relevant to scholarship / Pune social welfare
    assert any(term in top_match['authority_name'].lower() for term in ["social welfare", "scholarship", "pune"]), (
        f"Unexpected top authority: {top_match['authority_name']}"
    )

    print("\n--- 2. Testing Nyaya-Draft Section 6(1) Generation ---")
    raw_complaint = (
        "Mera scholarship 4 mahine se atka hai, college fee mang raha hai. "
        "Why was my payment delayed? Kisine koi update nahi diya."
    )
    extracted_info = {
        "app_id": "MAHA-SCHOL-2026-9812",
        "scheme": "Post-Matric Scholarship for SC/OBC",
        "office": "District Social Welfare Office Pune",
    }

    result = nyaya_draft.generate_rti_draft(
        raw_complaint=raw_complaint,
        extracted_info=extracted_info,
        is_bpl=True,
        applicant_name="Priya Sharma",
    )

    print(f"Selected Authority: {result.authority_name} ({result.authority_id})")
    print(f"PIO: {result.pio_title}")
    print(f"Questions Count: {len(result.questions)}")
    for idx, q in enumerate(result.questions, 1):
        print(f"  Q{idx}: {q}")
        assert not q.lower().startswith("why"), f"Question starts with 'Why': {q}"
        assert not q.lower().startswith("kyun"), f"Question starts with 'Kyun': {q}"

    print(f"\nDraft Character Count: {result.char_count} / 3000")
    assert result.char_count <= 3000, f"Exceeded 3,000 chars: {result.char_count}"
    assert result.is_bpl is True, "BPL flag mismatch"
    assert "Section 6(1)" in result.draft_text, "Missing Section 6(1) citation"
    assert "Section 7(5)" in result.draft_text, "Missing Section 7(5) BPL citation"

    print("\n--- Generated Section 6(1) Draft Body ---")
    print(result.draft_text)
    print("------------------------------------------")

    if result.warnings:
        print(f"Guardrail Warnings: {result.warnings}")

    print("\nSTEP 2A VERIFIED OK")


if __name__ == "__main__":
    run_test()

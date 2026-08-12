import json
from pathlib import Path

from parser.parser import build_standard_json


def test_build_standard_json_structure() -> None:
    pdf_path = Path("pdf_storage") / "sample.pdf"
    if not pdf_path.exists():
        return

    result = build_standard_json(pdf_path)

    assert isinstance(result, dict)
    assert "document_title" in result
    assert "document_type" in result
    assert "source_file" in result
    assert "sections" in result
    assert isinstance(result["sections"], list)
    if result["sections"]:
        first = result["sections"][0]
        assert "section_number" in first
        assert "title" in first
        assert "content" in first

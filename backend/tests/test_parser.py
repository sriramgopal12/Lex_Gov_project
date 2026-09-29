import json
from pathlib import Path

from parser.parser import _parse_sections, build_standard_json


def test_parse_sections_does_not_split_on_inline_section_references() -> None:
    text = """
7. Disposal of request.—A request under section 6 shall be answered within
the period specified in sub-section (1) of section 7.
8. Exemption from disclosure.—Information may be withheld.
"""

    sections = _parse_sections(text)

    assert [section["section_number"] for section in sections] == ["7", "8"]
    assert "section 6" in f'{sections[0]["title"]} {sections[0]["content"]}'


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

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - optional dependency
    fitz = None


DEFAULT_SCHEMA = {
    "document_title": "",
    "document_type": "legal_document",
    "source_file": "",
    "document_number": "",
    "publication_date": "",
    "issuing_authority": "",
    "summary": "",
    "sections": [],
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {
        "document_title": "",
        "document_number": "",
        "publication_date": "",
        "issuing_authority": "",
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        metadata["document_title"] = lines[0]

    for line in lines:
        if "no." in line.lower() or "number" in line.lower():
            if re.search(r"\b(?:no|number)\b", line, re.I):
                metadata["document_number"] = line
                break
        if re.search(r"\b(?:act|rule|regulation|notification|gazette)\b", line, re.I):
            metadata["issuing_authority"] = line

    return metadata


def _parse_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    pattern = re.compile(r"\b(section|sec\.?|s\.)\s*(\d+[A-Za-z]?)\b", re.I)

    lines = text.splitlines()
    current_section: dict[str, Any] | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section is not None:
                current_lines.append("")
            continue

        match = pattern.search(stripped)
        if match:
            if current_section is not None:
                current_section["content"] = "\n".join(current_lines).strip()
                sections.append(current_section)

            current_section = {
                "section_number": match.group(2),
                "title": stripped.replace(match.group(0), "", 1).strip(),
                "content": "",
            }
            current_lines = []
            continue

        if current_section is not None:
            current_lines.append(stripped)

    if current_section is not None:
        current_section["content"] = "\n".join(current_lines).strip()
        sections.append(current_section)

    cleaned_sections: list[dict[str, Any]] = []
    for section in sections:
        title = _normalize_text(section.get("title", ""))
        content = _normalize_text(section.get("content", ""))
        if title or content:
            cleaned_sections.append(
                {
                    "section_number": section.get("section_number", ""),
                    "title": title,
                    "content": content,
                }
            )

    return cleaned_sections


def _extract_text_from_pdf(pdf_path: str | Path) -> str:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed. Install 'pymupdf' to parse PDFs.")

    doc = fitz.open(str(pdf_path))
    text_parts: list[str] = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def build_standard_json(pdf_path: str | Path) -> dict[str, Any]:
    pdf_path = Path(pdf_path)
    text = _extract_text_from_pdf(pdf_path)

    metadata = _extract_metadata(text)
    sections = _parse_sections(text)

    output = dict(DEFAULT_SCHEMA)
    output["document_title"] = metadata["document_title"] or pdf_path.stem.replace("_", " ").title()
    output["source_file"] = str(pdf_path)
    output["document_number"] = metadata["document_number"]
    output["issuing_authority"] = metadata["issuing_authority"]
    output["summary"] = _normalize_text(text[:2000])
    output["sections"] = sections

    return output


def parse_document_to_json(pdf_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    result = build_standard_json(pdf_path)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result

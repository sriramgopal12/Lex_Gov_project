from uuid import UUID

from general_logic import documents


def test_build_document_filenames_uses_unique_identifier(monkeypatch) -> None:
	monkeypatch.setattr(documents, "uuid4", lambda: UUID("12345678-1234-5678-1234-567812345678"))

	document_key, pdf_filename, json_filename = documents.build_document_filenames("My Sample.pdf")

	assert document_key == "12345678123456781234567812345678"
	assert pdf_filename == "12345678123456781234567812345678_My_Sample.pdf"
	assert json_filename == "12345678123456781234567812345678_My_Sample.json"
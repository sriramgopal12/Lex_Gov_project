from uuid import UUID
from pathlib import Path

from general_logic import documents


def test_build_document_filenames_uses_unique_identifier(monkeypatch) -> None:
	monkeypatch.setattr(documents, "uuid4", lambda: UUID("12345678-1234-5678-1234-567812345678"))

	unique_identifier_name, pdf_filename, json_filename = documents.build_document_filenames("My Sample.pdf")

	assert unique_identifier_name == "12345678123456781234567812345678"
	assert pdf_filename == "12345678123456781234567812345678_My_Sample.pdf"
	assert json_filename == "12345678123456781234567812345678_My_Sample.json"


def test_store_document_persists_user_pdf_mapping(monkeypatch) -> None:
	class FakeCursor:
		def __init__(self) -> None:
			self.executed = []
			self._result = (
				1,
				7,
				"My Sample.pdf",
				"12345678123456781234567812345678",
				"My Sample.pdf",
				"12345678123456781234567812345678",
				"12345678123456781234567812345678_My_Sample.pdf",
				"12345678123456781234567812345678_My_Sample.json",
			)

		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def execute(self, query, params=None):
			self.executed.append((query, params))

		def fetchone(self):
			return self._result

	class FakeConnection:
		def __init__(self) -> None:
			self.cursor_obj = FakeCursor()

		def cursor(self):
			return self.cursor_obj

	class FakeConnectionManager:
		def __init__(self) -> None:
			self.connection = FakeConnection()

		def __enter__(self):
			return self.connection

		def __exit__(self, exc_type, exc, tb):
			return False

	manager = FakeConnectionManager()
	monkeypatch.setattr(documents, "get_document_connection", lambda: manager)

	result = documents.store_document(
		user_id=7,
		pdf_name="My Sample.pdf",
		unique_identifier_name="12345678123456781234567812345678",
		original_filename="My Sample.pdf",
		document_key="12345678123456781234567812345678",
		pdf_filename="12345678123456781234567812345678_My_Sample.pdf",
		json_filename="12345678123456781234567812345678_My_Sample.json",
	)

	assert result["user_id"] == 7
	assert result["pdf_name"] == "My Sample.pdf"
	assert result["unique_identifier_name"] == "12345678123456781234567812345678"
	assert manager.connection.cursor_obj.executed[0][0].lower().count("pdf_name") >= 1


def test_delete_document_removes_owned_resources_and_tolerates_missing_files(monkeypatch, tmp_path: Path) -> None:
	monkeypatch.chdir(tmp_path)
	(pdf_storage := tmp_path / "pdf_storage").mkdir()
	(json_storage := tmp_path / "json_storage").mkdir()
	(pdf_storage / "owned.pdf").write_bytes(b"pdf")
	(json_storage / "owned.json").write_text("{}")

	monkeypatch.setattr(
		documents,
		"get_document_for_user",
		lambda document_id, user_id: {
			"id": document_id,
			"user_id": user_id,
			"pdf_name": "owned.pdf",
			"pdf_filename": "owned.pdf",
			"json_filename": "owned.json",
			"status": "completed",
			"stage": "completed",
			"processing_error": None,
		},
	)

	class FakeCursor:
		rowcount = 1

		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def execute(self, query, params=None):
			self.params = params

	class FakeConnection:
		def __init__(self):
			self.cursor_obj = FakeCursor()

		def cursor(self):
			return self.cursor_obj

	class FakeManager:
		def __init__(self):
			self.connection = FakeConnection()

		def __enter__(self):
			return self.connection

		def __exit__(self, exc_type, exc, tb):
			return False

	monkeypatch.setattr(documents, "get_document_connection", lambda: FakeManager())

	assert documents.delete_document_for_user(12, 7) is True
	assert not (pdf_storage / "owned.pdf").exists()
	assert not (json_storage / "owned.json").exists()


def test_delete_document_rejects_documents_not_owned(monkeypatch) -> None:
	monkeypatch.setattr(documents, "get_document_for_user", lambda document_id, user_id: None)

	assert documents.delete_document_for_user(12, 7) is False
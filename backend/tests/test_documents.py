from uuid import UUID

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
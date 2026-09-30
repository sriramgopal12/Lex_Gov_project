from general_logic import chat_history


def test_delete_chat_record_scopes_delete_to_chat_user_and_document(monkeypatch) -> None:
	class FakeCursor:
		rowcount = 1

		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def execute(self, query, params=None):
			self.query = query
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

	manager = FakeManager()
	monkeypatch.setattr(chat_history, "get_connection", lambda: manager)

	assert chat_history.delete_chat_record(7, 12, 25) is True
	assert manager.connection.cursor_obj.params == (25, 7, 12)
	assert "id = %s" in manager.connection.cursor_obj.query
	assert "user_id = %s" in manager.connection.cursor_obj.query
	assert "document_id = %s" in manager.connection.cursor_obj.query
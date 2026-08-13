from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict, cast
from uuid import uuid4

from general_logic.auth import get_connection


class DocumentRecord(TypedDict):
	id: int
	user_id: int
	pdf_name: str
	unique_identifier_name: str
	original_filename: str
	document_key: str
	pdf_filename: str
	json_filename: str


class DocumentListItem(TypedDict):
	pdf_name: str
	unique_identifier_name: str
	pdf_filename: str
	json_filename: str


DOCUMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS documents (
	id SERIAL PRIMARY KEY,
	user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	pdf_name VARCHAR(255) NOT NULL,
	unique_identifier_name VARCHAR(80) NOT NULL UNIQUE,
	original_filename VARCHAR(255) NOT NULL,
	document_key VARCHAR(80) NOT NULL UNIQUE,
	pdf_filename VARCHAR(255) NOT NULL,
	json_filename VARCHAR(255) NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


@contextmanager
def get_document_connection():
	with get_connection() as connection:
		yield connection


def initialize_document_storage() -> None:
	with get_document_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(DOCUMENT_TABLE_SQL)
			cursor.execute(
				"""
				ALTER TABLE documents
				ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE documents
				ADD COLUMN IF NOT EXISTS pdf_name VARCHAR(255)
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE documents
				ADD COLUMN IF NOT EXISTS unique_identifier_name VARCHAR(80)
				"""
			)
			cursor.execute(
				"""
				UPDATE documents
				SET
					pdf_name = COALESCE(pdf_name, original_filename),
					unique_identifier_name = COALESCE(unique_identifier_name, document_key)
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE documents
				ALTER COLUMN pdf_name SET NOT NULL,
				ALTER COLUMN unique_identifier_name SET NOT NULL
				"""
			)


def _safe_file_stem(filename: str) -> str:
	stem = Path(filename).stem.strip().replace(" ", "_")
	return stem or "document"


def build_document_filenames(original_filename: str) -> tuple[str, str, str]:
	unique_identifier_name = uuid4().hex
	stem = _safe_file_stem(original_filename)
	pdf_filename = f"{unique_identifier_name}_{stem}.pdf"
	json_filename = f"{unique_identifier_name}_{stem}.json"
	return unique_identifier_name, pdf_filename, json_filename


def store_document(
	user_id: int,
	pdf_name: str,
	unique_identifier_name: str,
	original_filename: str,
	document_key: str,
	pdf_filename: str,
	json_filename: str,
) -> DocumentRecord:
	with get_document_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				INSERT INTO documents (
					user_id,
					pdf_name,
					unique_identifier_name,
					original_filename,
					document_key,
					pdf_filename,
					json_filename
				)
				VALUES (%s, %s, %s, %s, %s, %s, %s)
				RETURNING id, user_id, pdf_name, unique_identifier_name, original_filename, document_key, pdf_filename, json_filename
				""",
				(
					user_id,
					pdf_name,
					unique_identifier_name,
					original_filename,
					document_key,
					pdf_filename,
					json_filename,
				),
			)
			document = cursor.fetchone()

	if document is None:
		raise RuntimeError("Failed to store document metadata")

	document_id, stored_user_id, stored_pdf_name, stored_identifier_name, filename, key, stored_pdf, stored_json = cast(tuple[int, int, str, str, str, str, str, str], document)
	return {
		"id": document_id,
		"user_id": stored_user_id,
		"pdf_name": stored_pdf_name,
		"unique_identifier_name": stored_identifier_name,
		"original_filename": filename,
		"document_key": key,
		"pdf_filename": stored_pdf,
		"json_filename": stored_json,
	}


def list_documents_for_user(user_id: int) -> list[DocumentListItem]:
	with get_document_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT
					COALESCE(pdf_name, original_filename),
					COALESCE(unique_identifier_name, document_key),
					pdf_filename,
					json_filename
				FROM documents
				WHERE user_id = %s
				ORDER BY created_at DESC
				""",
				(user_id,),
			)
			rows = cursor.fetchall()

	return [
		{
			"pdf_name": cast(str, row[0]),
			"unique_identifier_name": cast(str, row[1]),
			"pdf_filename": cast(str, row[2]),
			"json_filename": cast(str, row[3]),
		}
		for row in rows
	]
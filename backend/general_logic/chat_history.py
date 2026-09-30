from __future__ import annotations

import json
from typing import TypedDict, cast

from general_logic.auth import get_connection
import logging


logger = logging.getLogger(__name__)


class ChatHistoryRecord(TypedDict):
    id: int
    question: str
    answer: str
    sources: list[dict[str, object]]
    simplified_answer: str | None
    answer_id: str
    created_at: str


CHAT_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    answer_id VARCHAR(64) NOT NULL UNIQUE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    simplified_answer TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def initialize_chat_history_storage() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CHAT_HISTORY_TABLE_SQL)


def save_chat_history(
    user_id: int,
    document_id: int,
    answer_id: str,
    question: str,
    answer: str,
    sources: list[dict[str, object]],
) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_history (user_id, document_id, answer_id, question, answer, sources)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (user_id, document_id, answer_id, question, answer, json.dumps(sources)),
            )
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to save chat history")
    return cast(int, row[0])


def update_simplified_answer(user_id: int, document_id: int, answer_id: str, answer: str) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE chat_history
                SET simplified_answer = %s
                WHERE user_id = %s AND document_id = %s AND answer_id = %s
                """,
                (answer, user_id, document_id, answer_id),
            )
            return cursor.rowcount == 1


def list_chat_history(user_id: int, document_id: int) -> list[ChatHistoryRecord]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, question, answer, sources, simplified_answer, answer_id, created_at::text
                FROM chat_history
                WHERE user_id = %s AND document_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (user_id, document_id),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": cast(int, row[0]),
            "question": cast(str, row[1]),
            "answer": cast(str, row[2]),
            "sources": cast(list[dict[str, object]], row[3]),
            "simplified_answer": cast(str | None, row[4]),
            "answer_id": cast(str, row[5]),
            "created_at": cast(str, row[6]),
        }
        for row in rows
    ]


def delete_chat_record(user_id: int, document_id: int, chat_id: int) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM chat_history
                WHERE id = %s AND user_id = %s AND document_id = %s
                """,
                (chat_id, user_id, document_id),
            )
            deleted = cursor.rowcount == 1

    logger.info(
        "Chat deletion completed: chat_id=%s, document_id=%s, user_id=%s, deleted=%s",
        chat_id,
        document_id,
        user_id,
        deleted,
    )
    return deleted

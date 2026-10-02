from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

JSON_STORAGE_DIR = Path(__file__).resolve().parent.parent / "json_storage"
logger = logging.getLogger(__name__)

TOP_K = 5
CANDIDATE_K = 10
MIN_RELEVANCE_SCORE = 0.25
SEMANTIC_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.25
METADATA_WEIGHT = 0.10
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z]+[a-z0-9]*", _normalize_text(value))
        if token not in _STOP_WORDS and len(token) > 1
    }


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _requested_section_numbers(value: str) -> set[str]:
    return {
        number.lower()
        for number in re.findall(
            r"\b(?:section|sec\.?|s\.)\s*(?:no\.?\s*)?(\d+[a-z]?)\b",
            value.lower(),
        )
    }


def _section_fields(section: dict[str, Any]) -> dict[str, str]:
    return {
        "section_number": _normalize_text(section.get("section_number", "")),
        "title": _normalize_text(section.get("title", section.get("heading", ""))),
        "heading": _normalize_text(section.get("heading", "")),
        "content": _normalize_text(section.get("content", section.get("text", ""))),
        "chapter": _normalize_text(section.get("chapter", "")),
        "act": _normalize_text(section.get("act", "")),
    }


@lru_cache(maxsize=1)
def _model():
    # Imported here so the slow model load happens once, on first use.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def _embed(texts: list[str]) -> np.ndarray:
    return _model().encode(texts, normalize_embeddings=True, convert_to_numpy=True)


def _section_text(section: Any) -> str:
    if not isinstance(section, dict):
        return ""
    # ponytail: the model reads ~256 tokens, so long sections are judged by their start; chunk them if that hurts recall.
    return f"{section.get('title', section.get('heading', ''))}. {section.get('content', section.get('text', ''))}"


def _section_vectors(document_data: dict[str, Any]) -> np.ndarray:
    vectors = document_data.get("_embeddings")
    if vectors is None or len(vectors) != len(document_data["sections"]):
        vectors = _embed([_section_text(section) for section in document_data["sections"]])
        document_data["_embeddings"] = vectors
    return vectors


def _semantic_score(question_vector: np.ndarray, section_vector: np.ndarray) -> float:
    # Vectors are normalised, so the dot product is the cosine similarity.
    return max(0.0, float(np.dot(question_vector, section_vector)))


def _keyword_score(
    question: str,
    question_tokens: set[str],
    requested_section_numbers: set[str],
    fields: dict[str, str],
) -> float:
    query_phrase = _normalize_text(question)
    title_tokens = _tokens(f"{fields['title']} {fields['heading']}")
    content_tokens = _tokens(fields["content"])
    title_overlap = len(question_tokens & title_tokens) / max(len(question_tokens), 1)
    content_overlap = len(question_tokens & content_tokens) / max(len(question_tokens), 1)
    score = (0.65 * title_overlap) + (0.35 * content_overlap)
    if query_phrase and len(query_phrase.split()) > 1 and any(
        query_phrase in fields[field] for field in ("title", "heading", "content", "chapter")
    ):
        score += 0.25
    if fields["section_number"] in requested_section_numbers:
        score += 0.75
    return min(1.0, score)


def _metadata_score(
    question_tokens: set[str],
    requested_section_numbers: set[str],
    fields: dict[str, str],
) -> float:
    score = 0.0
    if fields["section_number"] in requested_section_numbers:
        score += 1.0
    if question_tokens & _tokens(fields["title"]):
        score += 0.55
    if question_tokens & _tokens(fields["heading"]):
        score += 0.55
    if question_tokens & _tokens(fields["chapter"]):
        score += 0.25
    return min(1.0, score)


def _result_key(fields: dict[str, str], section: dict[str, Any]) -> tuple[str, str, str, str]:
    page = _normalize_text(section.get("page_number", section.get("page", "")))
    return fields["section_number"], fields["title"], page, fields["content"]


def load_document_json(json_filename: str) -> dict[str, Any]:
    safe_filename = Path(json_filename).name
    json_path = JSON_STORAGE_DIR / safe_filename
    if not json_path.is_file():
        raise FileNotFoundError(f"Structured document data was not found: {safe_filename}")

    with json_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise ValueError("Structured document data has an invalid format")

    # Section embeddings are cached next to the JSON; older documents get theirs built on first use.
    # ponytail: staleness is detected by row count only; delete the .npy if a JSON is edited in place.
    cache_path = json_path.with_suffix(".npy")
    cached = np.load(cache_path) if cache_path.is_file() else None
    if cached is not None and len(cached) == len(data["sections"]):
        data["_embeddings"] = cached
    else:
        np.save(cache_path, _section_vectors(data))

    return data


def retrieve_sections(
    document_data: dict[str, Any],
    question: str,
    top_k: int = TOP_K,
    candidate_k: int = CANDIDATE_K,
) -> list[dict[str, Any]]:
    if not isinstance(document_data, dict) or not isinstance(document_data.get("sections"), list):
        return []

    question = _normalize_text(question)
    question_tokens = _tokens(question)
    requested_section_numbers = _requested_section_numbers(question)
    if not question_tokens and not requested_section_numbers:
        return []

    question_vector = _embed([question])[0]
    section_vectors = _section_vectors(document_data)
    candidates: list[dict[str, Any]] = []
    for index, section in enumerate(document_data["sections"]):
        if not isinstance(section, dict):
            continue

        fields = _section_fields(section)
        if not any(fields[field] for field in ("section_number", "title", "heading", "content")):
            continue
        semantic_score = _semantic_score(question_vector, section_vectors[index])
        keyword_score = _keyword_score(question, question_tokens, requested_section_numbers, fields)
        metadata_score = _metadata_score(question_tokens, requested_section_numbers, fields)
        candidates.append(
            {
                "section": section,
                "fields": fields,
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "metadata_score": metadata_score,
            }
        )

    candidate_pool: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for signal in ("semantic_score", "keyword_score", "metadata_score"):
        for candidate in sorted(candidates, key=lambda item: item[signal], reverse=True)[:candidate_k]:
            candidate_pool[_result_key(candidate["fields"], candidate["section"])] = candidate

    results: list[dict[str, Any]] = []
    for candidate in candidate_pool.values():
        final_score = (
            SEMANTIC_WEIGHT * candidate["semantic_score"]
            + KEYWORD_WEIGHT * candidate["keyword_score"]
            + METADATA_WEIGHT * candidate["metadata_score"]
        )
        if final_score < MIN_RELEVANCE_SCORE:
            continue
        section = candidate["section"]
        fields = candidate["fields"]
        result = dict(section)
        result.update(
            {
                "section_number": section.get("section_number", ""),
                "title": section.get("title", section.get("heading", "")),
                "content": section.get("content", section.get("text", "")),
                "page_number": section.get("page_number", section.get("page")),
                "score": final_score,
                "final_score": final_score,
                "semantic_score": candidate["semantic_score"],
                "keyword_score": candidate["keyword_score"],
                "metadata_score": candidate["metadata_score"],
            }
        )
        results.append(result)

    results.sort(key=lambda item: item["final_score"], reverse=True)
    logger.info(
        "Retrieved %s sections for question %r: %s",
        len(results[:top_k]),
        question,
        ", ".join(
            f"Section {item.get('section_number', '')} ({item['final_score']:.2f})"
            for item in results[:3]
        ),
    )
    return results[:top_k]

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

JSON_STORAGE_DIR = Path(__file__).resolve().parent.parent / "json_storage"
logger = logging.getLogger(__name__)

TOP_K = 5
CANDIDATE_K = 10
MIN_RELEVANCE_SCORE = 0.25
SEMANTIC_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.25
METADATA_WEIGHT = 0.10

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
_SEMANTIC_GROUPS = (
    {"time", "period", "deadline", "limit", "期限"},
    {"provide", "providing", "provided", "give", "giving", "response", "respond"},
    {"request", "application", "applicant", "apply"},
    {"duty", "duties", "obligation", "obligations", "responsibility"},
    {"deny", "denied", "rejection", "reject", "refusal"},
    {"authority", "authorities", "officer", "official"},
    {"appeal", "appeals", "review", "remedy"},
)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z]+[a-z0-9]*", _normalize_text(value))
        if token not in _STOP_WORDS and len(token) > 1
    }


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _expanded_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in _SEMANTIC_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


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


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return numerator / denominator if denominator else 0.0


def _semantic_score(question_tokens: set[str], fields: dict[str, str]) -> float:
    query_vector = Counter(_expanded_tokens(question_tokens))
    section_vector = Counter(
        _expanded_tokens(_tokens(" ".join(fields[field] for field in ("title", "heading", "content", "chapter"))))
    )
    return min(1.0, _cosine_similarity(query_vector, section_vector) * 1.35)


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

    candidates: list[dict[str, Any]] = []
    for section in document_data.get("sections", []):
        if not isinstance(section, dict):
            continue

        fields = _section_fields(section)
        if not any(fields[field] for field in ("section_number", "title", "heading", "content")):
            continue
        semantic_score = _semantic_score(question_tokens, fields)
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

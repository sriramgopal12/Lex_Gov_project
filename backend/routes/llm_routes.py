from fastapi import APIRouter
from pydantic import BaseModel

from llm.qa import search_sections, ask_llm

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
def ask_question(request: QuestionRequest):
    relevant_sections = search_sections(request.question)

    if not relevant_sections:
        return {
            "answer": "No relevant legal sections were found.",
            "sections": []
        }

    answer = ask_llm(
        request.question,
        relevant_sections
    )

    return {
        "answer": answer,
        "sections": [
            {
                "section_number": section["section_number"],
                "title": section["title"]
            }
            for section in relevant_sections
        ]
    }
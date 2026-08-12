import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


# 1. Load environment variables

backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY was not found in backend/.env")

client = genai.Client(api_key=api_key)


# 2. Location of legal JSON

JSON_PATH = backend_dir / "json_storage" / "sections.json"


# 3. Load legal sections

def load_sections():
    with open(JSON_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


# 4. Search relevant sections

def search_sections(question):
    sections = load_sections()

    question_words = question.lower().split()

    results = []

    for section in sections:
        text = (
            section.get("title", "") + " " +
            section.get("content", "")
        ).lower()

        score = sum(word in text for word in question_words)

        if score > 0:
            results.append((score, section))

    results.sort(reverse=True, key=lambda x: x[0])

    return [section for score, section in results[:5]]


# 5. Ask Gemini using the retrieved legal sections

def ask_llm(question, relevant_sections):

    context = ""

    for section in relevant_sections:
        context += f"""
Section {section["section_number"]}
Title: {section["title"]}
Content: {section["content"]}

"""

    prompt = f"""
You are a legal information assistant.

Answer the user's question using ONLY the legal information
provided in the context below.

If the context does not contain enough information to answer
the question, clearly say that the provided legal document
does not contain enough information.

Do not invent laws or sections.

LEGAL CONTEXT:
{context}

USER QUESTION:
{question}

Give a clear and simple answer.
Mention the relevant section number when possible.
"""

    response = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    return response.output_text


# 6. Run the program

if __name__ == "__main__":

    question = input("Ask a legal question: ")

    relevant_sections = search_sections(question)

    if not relevant_sections:
        print("\nNo relevant legal sections found.")
    else:

        print("\nRelevant sections found:\n")

        for section in relevant_sections:
            print(
                f"Section {section['section_number']}: "
                f"{section['title']}"
            )

        answer = ask_llm(question, relevant_sections)

        print("\n" + "=" * 60)
        print("LLM ANSWER")
        print("=" * 60)
        print(answer)
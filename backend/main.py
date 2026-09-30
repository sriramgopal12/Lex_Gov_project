import json
from uuid import uuid4
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr

from general_logic.auth import (
	create_access_token,
	get_current_user_id,
	initialize_database,
	login_user,
	signup_user,
)
from general_logic.documents import (
	build_document_filenames,
	delete_document_for_user,
	get_document_for_user,
	initialize_document_storage,
	list_documents_for_user,
	store_document,
	update_document_status,
)
from general_logic.chat_history import (
	delete_chat_record,
	initialize_chat_history_storage,
	list_chat_history,
	save_chat_history,
	update_simplified_answer,
)
from parser import parse_document_to_json
from general_logic.retrieval import load_document_json, retrieve_sections
from general_logic.llm import (
	generate_document_explanation,
	generate_simpler_explanation,
	generate_suggested_questions,
)


load_dotenv()

app = FastAPI(title="Lex Gov API")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)


class SignupRequest(BaseModel):
	name: str
	email: EmailStr
	password: str

class LoginRequest(BaseModel):
	email: EmailStr
	password: str


class AskDocumentRequest(BaseModel):
	question: str


class SimplerExplanationRequest(BaseModel):
	answer_id: str


_SUGGESTION_CACHE: dict[tuple[int, str], list[str]] = {}
_ANSWER_CONTEXT_CACHE: dict[str, tuple[int, int, str, list[dict[str, object]]]] = {}


def _fallback_suggested_questions(document_data: dict[str, object]) -> list[str]:
	questions: list[str] = []
	seen_titles: set[str] = set()
	sections = document_data.get("sections", [])
	if not isinstance(sections, list):
		return questions
	for section in sections:
		if not isinstance(section, dict):
			continue
		title = str(section.get("title") or section.get("heading") or "").strip().rstrip(".")
		number = str(section.get("section_number") or "").strip()
		if not title or title.lower() in seen_titles:
			continue
		seen_titles.add(title.lower())
		questions.append(f"What does Section {number} say about {title}?" if number else f"What does the document say about {title}?")
		if len(questions) == 5:
			break
	return questions


@app.on_event("startup")
def startup() -> None:
	initialize_database()
	initialize_document_storage()
	initialize_chat_history_storage()


@app.get("/")
def root() -> dict[str, str]:
	return {"message": "Lex Gov API is running"}


@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest) -> dict[str, str]:
	try:
		user = signup_user(payload.name, payload.email, payload.password)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

	return {
		"message": "User created successfully",
		"user_id": str(user["id"]),
		"email": user["email"],
	}


@app.post("/login")
def login(payload: LoginRequest) -> dict[str, str]:
	user = login_user(payload.email, payload.password)
	if user is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid email or password",
		)

	return {
		"message": "Login successful",
		"user_id": str(user["id"]),
		"access_token": create_access_token(user["id"]),
		"token_type": "bearer",
		"name": user["name"],
		"email": user["email"],
	}


@app.post("/parse-document")
def parse_document(
	file: UploadFile = File(...),
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	if not file.filename or not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

	original_filename = Path(file.filename).name
	unique_identifier_name, pdf_filename, json_filename = build_document_filenames(original_filename)
	pdf_storage_path = Path("pdf_storage") / pdf_filename
	json_storage_path = Path("json_storage") / json_filename
	stored_document = None
	try:
		pdf_storage_path.parent.mkdir(parents=True, exist_ok=True)
		json_storage_path.parent.mkdir(parents=True, exist_ok=True)

		pdf_bytes = file.file.read()
		with open(pdf_storage_path, "wb") as handle:
			handle.write(pdf_bytes)

		stored_document = store_document(
			user_id=user_id,
			pdf_name=original_filename,
			unique_identifier_name=unique_identifier_name,
			original_filename=original_filename,
			document_key=unique_identifier_name,
			pdf_filename=pdf_filename,
			json_filename=json_filename,
			status="processing",
			stage="uploading",
		)
		update_document_status(stored_document["id"], user_id, "processing", "extracting_text")
		parse_document_to_json(pdf_storage_path, json_storage_path)
		update_document_status(stored_document["id"], user_id, "completed", "completed")

		return {
			"message": "Document parsed successfully",
			"document_id": stored_document["id"],
			"status": "completed",
			"stage": "completed",
		}
	except Exception as exc:  # pragma: no cover - defensive handling
		if stored_document is not None:
			update_document_status(stored_document["id"], user_id, "failed", "failed", "Unable to process this document")
		if pdf_storage_path.exists():
			pdf_storage_path.unlink()
		if json_storage_path.exists():
			json_storage_path.unlink()
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="Unable to process this document",
		) from exc


@app.get("/documents")
def list_user_documents(user_id: int = Depends(get_current_user_id)) -> dict[str, object]:
	documents = list_documents_for_user(user_id)
	return {
		"message": "Documents retrieved successfully",
		"documents": documents,
	}


@app.get("/documents/{document_id}/status")
def document_status(
	document_id: int,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	return {
		"document_id": document["id"],
		"status": document["status"],
		"stage": document["stage"],
		"error": document["processing_error"],
	}


@app.get("/documents/{document_id}/chat-history")
def document_chat_history(
	document_id: int,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	return {"document_id": document_id, "messages": list_chat_history(user_id, document_id)}


@app.delete("/documents/{document_id}/chat-history/{chat_id}")
def delete_chat_history_record(
	document_id: int,
	chat_id: int,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	if not delete_chat_record(user_id, document_id, chat_id):
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
	return {
		"success": True,
		"message": "Chat deleted successfully",
		"chat_id": chat_id,
	}


@app.delete("/documents/{document_id}")
def delete_document(
	document_id: int,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	if not delete_document_for_user(document_id, user_id):
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

	_SUGGESTION_CACHE.pop((user_id, document["json_filename"]), None)
	for answer_id, context in list(_ANSWER_CONTEXT_CACHE.items()):
		if context[0] == user_id and context[1] == document_id:
			_ANSWER_CONTEXT_CACHE.pop(answer_id, None)
	return {"success": True, "message": "Document deleted successfully"}


@app.get("/documents/{document_id}/suggested-questions")
def suggested_questions(
	document_id: int,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	if document["status"] != "completed":
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This document is not ready for questions")

	try:
		document_data = load_document_json(document["json_filename"])
	except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

	cache_key = (user_id, document["json_filename"])
	if cache_key in _SUGGESTION_CACHE:
		return {"questions": _SUGGESTION_CACHE[cache_key]}

	sections = document_data.get("sections", [])
	if not isinstance(sections, list):
		return {"questions": []}
	question_seed = "purpose rights duties obligations procedure time limit penalties appeal exemptions"
	relevant_sections = retrieve_sections(document_data, question_seed, top_k=10, candidate_k=20)
	if not relevant_sections:
		relevant_sections = [section for section in sections if isinstance(section, dict)][:10]
	try:
		questions = generate_suggested_questions(relevant_sections, document["pdf_name"])
	except (RuntimeError, ValueError, json.JSONDecodeError):
		questions = _fallback_suggested_questions(document_data)

	_SUGGESTION_CACHE[cache_key] = questions[:6]
	return {"questions": _SUGGESTION_CACHE[cache_key]}


@app.get("/documents/{document_id}/pdf")
def get_document_pdf(
	document_id: int,
	user_id: int = Depends(get_current_user_id),
) -> FileResponse:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

	pdf_path = Path("pdf_storage") / Path(document["pdf_filename"]).name
	if not pdf_path.is_file():
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original PDF not found")
	return FileResponse(pdf_path, media_type="application/pdf", filename=document["pdf_name"])


@app.post("/documents/{document_id}/ask")
def ask_document_question(
	document_id: int,
	payload: AskDocumentRequest,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	question = payload.question.strip()
	if document_id <= 0:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please provide a valid document ID")
	if not question:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please ask a question")
	if len(question) > 2000:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question is too long")

	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
	if document["status"] != "completed":
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This document is not ready for questions")

	try:
		document_data = load_document_json(document["json_filename"])
		retrieved_sections = retrieve_sections(document_data, question)
	except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

	if not retrieved_sections:
		answer_id = uuid4().hex
		history_id = save_chat_history(user_id, document_id, answer_id, question, "I could not find sufficient information about that question in this document.", [])
		return {
			"document": {"id": document["id"], "name": document["pdf_name"]},
			"answer_id": answer_id,
			"history_id": history_id,
			"answer": "I could not find sufficient information about that question in this document.",
			"found_information": False,
			"sources": [],
		}

	try:
		answer, found_information = generate_document_explanation(
			question,
			retrieved_sections,
			document["pdf_name"],
		)
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

	sources = [
		{
			"section_number": section.get("section_number", ""),
			"title": section.get("title", ""),
			"page": section.get("page_number"),
			"text": section.get("content", ""),
		}
		for section in retrieved_sections
	]
	answer_id = uuid4().hex
	history_id = save_chat_history(user_id, document_id, answer_id, question, answer, sources)
	_ANSWER_CONTEXT_CACHE[answer_id] = (user_id, document_id, question, retrieved_sections)
	return {
		"document": {"id": document["id"], "name": document["pdf_name"]},
		"answer_id": answer_id,
		"history_id": history_id,
		"answer": answer,
		"found_information": found_information,
		"sources": sources,
	}


@app.post("/documents/{document_id}/simpler")
def simplify_document_answer(
	document_id: int,
	payload: SimplerExplanationRequest,
	user_id: int = Depends(get_current_user_id),
) -> dict[str, object]:
	document = get_document_for_user(document_id, user_id)
	if document is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

	context = _ANSWER_CONTEXT_CACHE.get(payload.answer_id)
	if context is None or context[0] != user_id or context[1] != document_id:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer context not found")

	_, _, question, retrieved_sections = context
	try:
		answer, found_information = generate_simpler_explanation(
			question,
			retrieved_sections,
			document["pdf_name"],
		)
	except RuntimeError as exc:
		raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

	update_simplified_answer(user_id, document_id, payload.answer_id, answer)
	return {"answer": answer, "found_information": found_information}


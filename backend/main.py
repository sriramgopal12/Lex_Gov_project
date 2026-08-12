from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr

from general_logic.auth import (
	initialize_database,
	login_user,
	signup_user,
)
from general_logic.documents import (
	build_document_filenames,
	initialize_document_storage,
	list_documents_for_user,
	store_document,
)
from parser import parse_document_to_json


load_dotenv()

app = FastAPI(title="Lex Gov API")


class SignupRequest(BaseModel):
	name: str
	email: EmailStr
	password: str

class LoginRequest(BaseModel):
	email: EmailStr
	password: str


@app.on_event("startup")
def startup() -> None:
	initialize_database()
	initialize_document_storage()


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
		"name": user["name"],
		"email": user["email"],
	}


@app.post("/parse-document")
def parse_document(user_id: int = Form(...), file: UploadFile = File(...)) -> dict[str, object]:
	if user_id <= 0:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please provide a valid user_id")

	if not file.filename or not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

	original_filename = Path(file.filename).name
	document_key, pdf_filename, json_filename = build_document_filenames(original_filename)
	pdf_storage_path = Path("pdf_storage") / pdf_filename
	json_storage_path = Path("json_storage") / json_filename
	try:
		pdf_storage_path.parent.mkdir(parents=True, exist_ok=True)
		json_storage_path.parent.mkdir(parents=True, exist_ok=True)

		pdf_bytes = file.file.read()
		with open(pdf_storage_path, "wb") as handle:
			handle.write(pdf_bytes)

		parse_document_to_json(pdf_storage_path, json_storage_path)
		store_document(
			user_id=user_id,
			original_filename=original_filename,
			document_key=document_key,
			pdf_filename=pdf_filename,
			json_filename=json_filename,
		)

		return {
			"message": "Document parsed successfully",
		}
	except Exception as exc:  # pragma: no cover - defensive handling
		if pdf_storage_path.exists():
			pdf_storage_path.unlink()
		if json_storage_path.exists():
			json_storage_path.unlink()
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.get("/documents/{user_id}")
def list_user_documents(user_id: int) -> dict[str, object]:
	if user_id <= 0:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please provide a valid user_id")

	documents = list_documents_for_user(user_id)
	return {
		"message": "Documents retrieved successfully",
		"documents": documents,
	}


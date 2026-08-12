import os

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr

from general_logic.auth import (
	initialize_database,
	login_user,
	signup_user,
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
def parse_document(file: UploadFile = File(...)) -> dict[str, object]:
	if not file.filename or not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a PDF file")

	temp_path = None
	try:
		temp_path = f"pdf_storage/{file.filename}"
		with open(temp_path, "wb") as handle:
			handle.write(file.file.read())

		result = parse_document_to_json(temp_path)
		return {
			"message": "Document parsed successfully",
			"document": result,
		}
	except Exception as exc:  # pragma: no cover - defensive handling
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
	finally:
		if temp_path and os.path.exists(temp_path):
			os.remove(temp_path)


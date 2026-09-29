import os
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from typing import TypedDict, cast

import bcrypt
import jwt
import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class UserRecord(TypedDict):
    id: int
    name: str
    email: str


class UserLoginRecord(UserRecord):
    password_hash: str


_bearer_scheme = HTTPBearer()


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not set")
    return secret


def create_access_token(user_id: int) -> str:
    expires_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> int:
    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def _password_exceeds_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > 72


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return database_url


@contextmanager
def get_connection():
    connection = psycopg.connect(get_database_url())
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )


def hash_password(password: str) -> str:
    if _password_exceeds_bcrypt_limit(password):
        raise ValueError("Password must be 72 bytes or fewer")

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    if _password_exceeds_bcrypt_limit(plain_password):
        return False

    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def signup_user(name: str, email: str, password: str) -> UserRecord:
    normalized_email = email.strip().lower()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (normalized_email,),
            )
            existing_user = cursor.fetchone()
            if existing_user is not None:
                raise ValueError("Email already registered")

            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, name, email
                """,
                (name.strip(), normalized_email, hash_password(password)),
            )
            user = cursor.fetchone()

    if user is None:
        raise RuntimeError("Failed to create user")

    user_id, created_name, created_email = cast(tuple[int, str, str], user)
    return {
        "id": user_id,
        "name": created_name,
        "email": created_email,
    }


def login_user(email: str, password: str) -> UserLoginRecord | None:
    normalized_email = email.strip().lower()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email, password_hash FROM users WHERE email = %s",
                (normalized_email,),
            )
            user = cursor.fetchone()

    if user is None:
        return None

    user_id, name, email_address, password_hash = cast(tuple[int, str, str, str], user)

    if not verify_password(password, password_hash):
        return None

    return cast(
        UserLoginRecord,
        {
        "id": user_id,
        "name": name,
        "email": email_address,
        },
    )

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import HTTPException
import jwt
from passlib.context import CryptContext
from app.core.config import settings

# SHA-256 preprocessing preserves the complete password beyond bcrypt's
# 72-byte limit. Legacy bcrypt hashes remain verifiable during recovery.
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except (TypeError, ValueError):
        return False


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def password_needs_upgrade(hashed: str) -> bool:
    return pwd_context.needs_update(hashed)


def validate_password(password: str) -> None:
    if len(password) < settings.password_min_length:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {settings.password_min_length} characters",
        )
    if not any(ch.islower() for ch in password) or not any(
        ch.isupper() for ch in password
    ):
        raise HTTPException(
            status_code=422,
            detail="Password must contain upper- and lower-case letters",
        )
    if not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=422, detail="Password must contain a number")
    if not any(not ch.isalnum() for ch in password):
        raise HTTPException(status_code=422, detail="Password must contain a symbol")


def new_token_id() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(subject: str, *, token_id: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "jti": token_id,
        "ver": token_version,
        "iat": now,
        "exp": expires,
        "typ": "access",
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

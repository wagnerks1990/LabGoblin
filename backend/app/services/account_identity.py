"""Canonical email identifiers without changing stable legacy account handles."""

from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.models import User


def normalize_email(value):
    try:
        return validate_email(
            str(value).strip(), check_deliverability=False, test_environment=True
        ).normalized.lower()
    except EmailNotValidError:
        raise HTTPException(422, "Enter a valid account email address") from None


def email_column():
    return func.lower(func.rtrim(func.ltrim(User.email)))


def ensure_email_available(db, email, *, exclude_id=None):
    query = db.query(User.id).filter(email_column() == email)
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    if query.first():
        raise HTTPException(409, "An account already uses this email address")


def new_account_handle():
    return "user-" + uuid4().hex


def flush_account(db):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "An account already uses this email or account name"
        ) from None

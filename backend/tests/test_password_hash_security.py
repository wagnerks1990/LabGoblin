"""Preserve full password identity and existing bcrypt credential compatibility."""

from passlib.hash import bcrypt
import pytest

from app.services.security import hash_password, validate_password, verify_password


@pytest.mark.parametrize("prefix", ["A1!" + "a" * 69, "A1!" + "é" * 36])
def test_distinct_long_passwords_do_not_authenticate_each_other(prefix):
    first = prefix + "first"
    second = prefix + "second"
    validate_password(first)
    hashed = hash_password(first)
    assert hashed.startswith("$bcrypt-sha256$")
    assert verify_password(first, hashed)
    assert not verify_password(second, hashed)


def test_existing_bcrypt_credentials_remain_verifiable():
    password = "Synthetic-legacy-password-42!"
    legacy_hash = bcrypt.hash(password)
    assert verify_password(password, legacy_hash)
    assert not verify_password("Wrong-synthetic-password-42!", legacy_hash)

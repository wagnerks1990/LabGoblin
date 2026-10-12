"""Regression coverage for the PyJWT security upgrade; no external services."""

import base64
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import jwt
import pytest

from app.api import deps

SECRET = "dependency-regression-only-secret-32-bytes"


class NoDatabaseAccess:
    def query(self, _model):
        pytest.fail("Invalid JWT reached the database")


@pytest.mark.parametrize("case", ["unsigned", "algorithm", "key", "expired", "header"])
def test_invalid_access_tokens_fail_before_database(monkeypatch, case):
    monkeypatch.setattr(deps.settings, "jwt_secret_key", SECRET)
    monkeypatch.setattr(deps.settings, "jwt_algorithm", "HS256")
    claims = {"sub": "alice", "jti": "session", "ver": 1, "typ": "access"}
    if case == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    algorithm = {"unsigned": "none", "algorithm": "HS384"}.get(case, "HS256")
    key = "" if case == "unsigned" else SECRET + ("wrong" if case == "key" else "")
    token = jwt.encode(claims, key, algorithm=algorithm)
    if case == "header":
        header = base64.urlsafe_b64encode(b"[" * 2000 + b"0" + b"]" * 2000)
        token = header.decode().rstrip("=") + "." + token.split(".", 1)[1]
    with pytest.raises(HTTPException) as error:
        deps.get_user_from_token(token, NoDatabaseAccess())
    assert error.value.status_code == 401


def test_unverified_decode_does_not_disable_later_claim_validation():
    options = {"verify_signature": False}
    token = jwt.encode({"exp": 1}, SECRET, algorithm="HS256")
    jwt.decode(token, options=options)
    assert options == {"verify_signature": False}
    options["verify_signature"] = True
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, SECRET, algorithms=["HS256"], options=options)


def test_deep_payload_raises_documented_token_error():
    payload = base64.urlsafe_b64encode(b"[" * 2000 + b"0" + b"]" * 2000)
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}')
    token = header.decode().rstrip("=") + "." + payload.decode().rstrip("=") + ".AA"
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token, options={"verify_signature": False})


def test_asymmetric_der_key_cannot_be_used_as_hmac_secret():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with pytest.raises(jwt.InvalidKeyError):
        jwt.encode({"sub": "alice"}, public_der, algorithm="HS256")

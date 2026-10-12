"""Exercise the real password backend after dependency upgrades."""

from app.services.security import hash_password, verify_password


def test_bcrypt_backend_initializes_and_round_trips():
    password = "Synthetic-lab-password-42!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Wrong-synthetic-password-42!", hashed)

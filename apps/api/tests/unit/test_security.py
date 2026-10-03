from __future__ import annotations

import base64
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from argon2 import PasswordHasher

from app.core.security import (
    AccessClaims,
    InvalidAccessToken,
    PasswordService,
    TokenService,
    hash_opaque_token,
    new_opaque_token,
)

KEY = "test-only-signing-key-32-characters"
NOW = datetime(2030, 1, 1, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
FAMILY_ID = UUID("22222222-2222-4222-8222-222222222222")


def test_password_hash_is_salted_argon2id_and_verifies() -> None:
    service = PasswordService()
    password = " correct horse battery staple đ"

    first = service.hash(password)
    second = service.hash(password)

    assert first.startswith("$argon2id$")
    assert password not in first
    assert first != second
    assert service.verify(password, first) is True
    assert service.verify("wrong-password", first) is False
    assert service.verify(password.strip(), first) is False
    assert service.needs_rehash(first) is False


def test_password_service_requests_rehash_for_obsolete_parameters() -> None:
    obsolete = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1).hash("old password")
    service = PasswordService()

    assert service.verify("old password", obsolete) is True
    assert service.needs_rehash(obsolete) is True


@pytest.mark.parametrize("encoded", ["", "plain-password", "$argon2id$invalid"])
def test_invalid_password_hash_is_rejected(encoded: str) -> None:
    assert PasswordService().verify("password", encoded) is False


def test_access_token_contains_required_claims_and_decodes_with_injected_clock() -> None:
    service = TokenService(KEY, clock=lambda: NOW)

    token = service.create_access_token(USER_ID, FAMILY_ID)
    payload = jwt.decode(token, KEY, algorithms=["HS256"], options={"verify_iat": False})

    assert payload == {
        "sub": str(USER_ID),
        "sid": str(FAMILY_ID),
        "type": "access",
        "iat": 1893456000,
        "exp": 1893456900,
    }
    assert service.decode_access_token(token) == AccessClaims(
        USER_ID, FAMILY_ID, NOW, NOW + timedelta(minutes=15)
    )


def test_access_token_uses_configured_lifetime() -> None:
    service = TokenService(KEY, access_token_minutes=3, clock=lambda: NOW)

    claims = service.decode_access_token(service.create_access_token(USER_ID, FAMILY_ID))

    assert claims.expires_at == NOW + timedelta(minutes=3)


def test_access_claims_are_immutable() -> None:
    claims = AccessClaims(USER_ID, FAMILY_ID, NOW, NOW + timedelta(minutes=15))

    with pytest.raises(FrozenInstanceError):
        claims.user_id = FAMILY_ID  # type: ignore[misc]


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("type", "refresh"),
        ("sub", "not-a-uuid"),
        ("sid", "not-a-uuid"),
        ("sid", 123),
        ("sub", None),
        ("iat", 1893456001),
        ("iat", "1893456000"),
        ("iat", True),
        ("exp", 1893456000),
        ("exp", None),
        ("exp", "1893456900"),
        ("exp", 10**30),
    ],
)
def test_invalid_access_claims_have_one_sanitized_error(claim: str, value: object) -> None:
    payload: dict[str, object] = {
        "sub": str(USER_ID),
        "sid": str(FAMILY_ID),
        "type": "access",
        "iat": 1893456000,
        "exp": 1893456900,
    }
    payload[claim] = value
    token = jwt.encode(payload, KEY, algorithm="HS256")

    with pytest.raises(InvalidAccessToken) as error:
        TokenService(KEY, clock=lambda: NOW).decode_access_token(token)

    assert str(error.value) == "Invalid access token"
    assert token not in str(error.value)
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize("claim", ["sub", "sid", "type", "iat", "exp"])
def test_access_token_requires_all_claims(claim: str) -> None:
    payload = {
        "sub": str(USER_ID),
        "sid": str(FAMILY_ID),
        "type": "access",
        "iat": 1893456000,
        "exp": 1893456900,
    }
    del payload[claim]

    with pytest.raises(InvalidAccessToken, match=r"^Invalid access token$"):
        TokenService(KEY, clock=lambda: NOW).decode_access_token(
            jwt.encode(payload, KEY, algorithm="HS256")
        )


def test_access_token_invalid_signature_has_sanitized_error() -> None:
    token = TokenService(KEY, clock=lambda: NOW).create_access_token(USER_ID, FAMILY_ID)

    with pytest.raises(InvalidAccessToken, match=r"^Invalid access token$"):
        TokenService("another-signing-key-32-characters", clock=lambda: NOW).decode_access_token(
            token
        )


@pytest.mark.parametrize("algorithm", ["HS384", "none"])
def test_access_token_cannot_choose_algorithm(algorithm: str) -> None:
    payload = {
        "sub": str(USER_ID),
        "sid": str(FAMILY_ID),
        "type": "access",
        "iat": 1893456000,
        "exp": 1893456900,
    }
    signing_key = "x" * 64
    token = jwt.encode(payload, signing_key if algorithm != "none" else None, algorithm=algorithm)

    with pytest.raises(InvalidAccessToken, match=r"^Invalid access token$"):
        TokenService(signing_key, clock=lambda: NOW).decode_access_token(token)


@pytest.mark.parametrize("token", ["", "not-a-jwt", "one.two.three"])
def test_malformed_access_token_has_sanitized_error(token: str) -> None:
    with pytest.raises(InvalidAccessToken, match=r"^Invalid access token$"):
        TokenService(KEY, clock=lambda: NOW).decode_access_token(token)


def test_access_token_expires_at_exact_boundary_using_injected_clock() -> None:
    token = TokenService(KEY, clock=lambda: NOW).create_access_token(USER_ID, FAMILY_ID)

    assert TokenService(KEY, clock=lambda: NOW + timedelta(seconds=899)).decode_access_token(token)
    with pytest.raises(InvalidAccessToken, match=r"^Invalid access token$"):
        TokenService(KEY, clock=lambda: NOW + timedelta(minutes=15)).decode_access_token(token)


def test_opaque_tokens_contain_at_least_256_random_bits_and_differ() -> None:
    first = new_opaque_token()
    second = new_opaque_token()

    assert len(base64.urlsafe_b64decode(first + "=" * (-len(first) % 4))) >= 32
    assert first != second


def test_opaque_token_hash_is_deterministic_sha256_digest() -> None:
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    assert hash_opaque_token("abc") == expected
    assert hash_opaque_token("abc") == hash_opaque_token("abc")
    assert hash_opaque_token("abc") != "abc"

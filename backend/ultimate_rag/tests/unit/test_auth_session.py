from __future__ import annotations

import time

import pytest

from ultimate_rag.auth.session import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    h = hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert verify_password("s3cret-pass", h) is True
    assert verify_password("wrong", h) is False


def test_token_round_trip():
    token = create_access_token(user_id="user_1", tenant_id="tenant_1", email="a@acme.test")
    assert token
    payload = decode_access_token(token)
    assert payload.sub == "user_1"
    assert payload.tenant_id == "tenant_1"
    assert payload.email == "a@acme.test"
    assert payload.exp > int(time.time())


def test_token_invalid_signature():
    token = create_access_token(user_id="u", tenant_id="t")
    tampered = token[:-5] + "AAAAA"
    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_token_expired():
    token = create_access_token(user_id="u", tenant_id="t", expires_seconds=-1)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_token_missing_fields_rejected():
    from jose import jwt

    from ultimate_rag.core.config import get_settings

    settings = get_settings()
    raw = jwt.encode({"foo": "bar"}, settings.secret_key.get_secret_value(), algorithm="HS256")
    with pytest.raises(TokenError):
        decode_access_token(raw)


def test_refresh_token_round_trip():
    token = create_refresh_token(user_id="user_1", tenant_id="tenant_1")
    payload = decode_refresh_token(token)
    assert payload.sub == "user_1"
    assert payload.tenant_id == "tenant_1"
    assert payload.exp > int(time.time())


def test_refresh_token_rejects_access_token():
    access = create_access_token(user_id="u", tenant_id="t")
    with pytest.raises(TokenError):
        decode_refresh_token(access)


def test_refresh_token_expired():
    token = create_refresh_token(user_id="u", tenant_id="t", expires_seconds=-1)
    with pytest.raises(TokenError):
        decode_refresh_token(token)

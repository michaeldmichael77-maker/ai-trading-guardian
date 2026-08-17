"""Tests for the password-protection layer (critical for internet deployment)."""

import importlib
import os

import pytest

from trading_bot import auth


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("GUARDIAN_PASSWORD", raising=False)
    monkeypatch.delenv("GUARDIAN_SECRET", raising=False)
    yield


def test_disabled_without_password():
    assert auth.is_enabled() is False


def test_enabled_with_password(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    assert auth.is_enabled() is True


def test_check_password(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    assert auth.check_password("hunter2") is True
    assert auth.check_password("wrong") is False
    assert auth.check_password("") is False


def test_check_password_false_when_unset():
    assert auth.check_password("anything") is False


def test_token_roundtrip(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    token = auth.make_token()
    assert auth.verify_token(token) is True


def test_token_rejected_for_wrong_password(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    token = auth.make_token()
    # Change the password -> old token must no longer verify.
    monkeypatch.setenv("GUARDIAN_PASSWORD", "different")
    assert auth.verify_token(token) is False


def test_forged_token_rejected(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    assert auth.verify_token("9999999999.deadbeef") is False
    assert auth.verify_token("garbage") is False
    assert auth.verify_token("") is False


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setenv("GUARDIAN_PASSWORD", "hunter2")
    # Build a token that already expired.
    import hmac, hashlib
    expiry = "1000000000"  # year 2001
    sig = hmac.new(auth._secret(), expiry.encode(), hashlib.sha256).hexdigest()
    assert auth.verify_token(f"{expiry}.{sig}") is False

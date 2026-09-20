"""Ragenie schema contract tests: pin the API shapes services exchange.

Each service's schemas import without heavy dependencies, so these
tests pin validation behavior directly: required fields, defaults,
and rejection of out-of-range input.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def _load(service: str, filename: str):
    # Load by path: every service names its package `schemas`, so plain
    # imports collide in sys.modules.
    name = f"ragenie_{service.replace('-', '_')}_schemas"
    path = ROOT / "services" / service / "app" / "schemas" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


auth = _load("auth-service", "auth.py")
chat = _load("llm-gateway-service", "llm.py")
conv = _load("conversation-service", "conversations.py")


class TestAuthSchemas:
    def test_register_accepts_valid(self):
        user = auth.UserRegister(
            email="ada@example.com", username="ada", password="s3cur3-pass"
        )
        assert user.email == "ada@example.com"

    def test_register_rejects_bad_email(self):
        with pytest.raises(ValidationError):
            auth.UserRegister(email="not-an-email", username="ada", password="s3cur3-pass")

    def test_register_rejects_short_credentials(self):
        with pytest.raises(ValidationError):
            auth.UserRegister(email="a@b.co", username="ab", password="s3cur3-pass")
        with pytest.raises(ValidationError):
            auth.UserRegister(email="a@b.co", username="ada", password="short")

    def test_token_defaults_bearer(self):
        token = auth.Token(access_token="a", refresh_token="r")
        assert token.token_type == "bearer"

    def test_password_reset_rejects_short_password(self):
        with pytest.raises(ValidationError):
            auth.PasswordReset(token="t", new_password="short")


class TestChatSchemas:
    def test_request_applies_defaults(self):
        req = chat.ChatRequest(
            model="gpt-4", messages=[{"role": "user", "content": "hi"}]
        )
        assert req.temperature == 0.7
        assert req.max_tokens == 4096
        assert req.stream is False

    def test_request_rejects_bad_ranges(self):
        with pytest.raises(ValidationError):
            chat.ChatRequest(
                model="gpt-4", messages=[], temperature=2.5
            )
        with pytest.raises(ValidationError):
            chat.ChatRequest(
                model="gpt-4", messages=[], max_tokens=0
            )

    def test_message_requires_role_and_content(self):
        with pytest.raises(ValidationError):
            chat.MessageInput(role="user")
        msg = chat.MessageInput(role="user", content="hi")
        assert msg.content == "hi"


class TestConversationSchemas:
    def test_create_defaults_title(self):
        created = conv.ConversationCreate()
        assert created.title == "New Conversation"

    def test_message_role_is_constrained(self):
        msg = conv.MessageCreate(role="user", content="hi")
        assert msg.role == "user"
        with pytest.raises(ValidationError):
            conv.MessageCreate(role="admin", content="hi")

    def test_response_requires_ids(self):
        with pytest.raises(ValidationError):
            conv.MessageResponse(role="user", content="hi")

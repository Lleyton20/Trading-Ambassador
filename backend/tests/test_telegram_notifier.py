"""Tests for app/alerts/telegram_notifier.py. Never touches the real
Telegram API - the "configured" path is checked by monkeypatching httpx."""
from __future__ import annotations

import httpx

from app.alerts.telegram_notifier import send_telegram_message


def test_noop_when_not_configured():
    assert send_telegram_message("", "", "hello") is False
    assert send_telegram_message("token", "", "hello") is False
    assert send_telegram_message("", "chat-id", "hello") is False


def test_sends_when_configured(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(httpx, "post", _fake_post)

    result = send_telegram_message("my-token", "my-chat-id", "price entered a zone")

    assert result is True
    assert captured["url"] == "https://api.telegram.org/bot my-token/sendMessage".replace(" ", "")
    assert captured["json"] == {"chat_id": "my-chat-id", "text": "price entered a zone"}


def test_returns_false_on_http_error(monkeypatch):
    def _fake_post(url, json, timeout):
        raise httpx.ConnectError("network down", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", _fake_post)

    assert send_telegram_message("my-token", "my-chat-id", "hello") is False

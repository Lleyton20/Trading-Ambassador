"""
Sends an alert message to Telegram via the Bot API.

Deliberately a no-op (logs and returns) when `telegram_bot_token` /
`telegram_chat_id` aren't configured, rather than raising - so
app/alerts/watcher.py (and its tests) never require a real Telegram bot
to exist. Get a token from @BotFather and your chat ID from
https://api.telegram.org/bot<token>/getUpdates after messaging the bot
once - see README "Alerts" for the full walkthrough.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def send_telegram_message(bot_token: str, chat_id: str, text: str, *, timeout: float = 10.0) -> bool:
    """Returns True if the message was sent, False if skipped (not configured) or it failed."""
    if not bot_token or not chat_id:
        logger.info("Telegram not configured, skipping alert: %s", text)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=timeout)
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Failed to send Telegram alert")
        return False

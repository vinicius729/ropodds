"""Telegram Bot for sending odds alerts and reports.

Uses raw Telegram HTTP API via httpx — no dependency on python-telegram-bot
or cryptography, which avoids native extension issues on some platforms.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

# Telegram message limit
MAX_MESSAGE_LENGTH = 4096

# Brasilia timezone (UTC-3)
BRT = timezone(timedelta(hours=-3))

# Telegram API base URL
API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    """Sends messages to a Telegram group via raw HTTP API."""

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID

    def _validate(self):
        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN não configurado. "
                "Configure no arquivo .env ou variável de ambiente."
            )
        if not self.chat_id:
            raise ValueError(
                "TELEGRAM_CHAT_ID não configurado. "
                "Configure no arquivo .env ou variável de ambiente."
            )

    def _api_url(self, method: str) -> str:
        return API_BASE.format(token=self.token, method=method)

    async def _call_api(self, method: str, payload: dict) -> dict:
        """Call Telegram Bot API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self._api_url(method), json=payload)
            data = resp.json()
            if not data.get("ok"):
                raise Exception(f"Telegram API error: {data.get('description', 'unknown')}")
            return data

    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a text message to the configured group."""
        self._validate()

        try:
            chunks = self._split_message(text)

            for chunk in chunks:
                try:
                    await self._call_api("sendMessage", {
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": parse_mode,
                    })
                except Exception:
                    # Retry without parse_mode if markdown fails
                    logger.warning("Markdown parse failed, retrying as plain text")
                    await self._call_api("sendMessage", {
                        "chat_id": self.chat_id,
                        "text": chunk,
                    })

                if len(chunks) > 1:
                    await asyncio.sleep(1)  # Rate limiting

            logger.info(f"Telegram: Sent {len(chunks)} message(s)")
            return True

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_alert(self, alert_text: str) -> bool:
        """Send an alert notification."""
        return await self.send_message(alert_text)

    async def send_report(self, report_text: str) -> bool:
        """Send a full report."""
        return await self.send_message(report_text)

    def _split_message(self, text: str) -> list[str]:
        """Split a message into chunks respecting Telegram's limit."""
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []

        # Split by section separators first
        sections = text.split("\n---\n")
        buf = ""

        for section in sections:
            candidate = buf + ("\n---\n" if buf else "") + section

            if len(candidate) > MAX_MESSAGE_LENGTH:
                if buf:
                    chunks.append(buf)

                # If a single section exceeds limit, split by lines
                if len(section) > MAX_MESSAGE_LENGTH:
                    lines = section.split("\n")
                    buf = ""
                    for line in lines:
                        if len(buf) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                            chunks.append(buf)
                            buf = line
                        else:
                            buf = buf + "\n" + line if buf else line
                else:
                    buf = section
            else:
                buf = candidate

        if buf:
            chunks.append(buf)

        return chunks

    async def test_connection(self) -> bool:
        """Test the bot connection and send a test message."""
        self._validate()
        try:
            data = await self._call_api("getMe", {})
            username = data.get("result", {}).get("username", "unknown")
            logger.info(f"Telegram bot connected: @{username}")

            now = datetime.now(BRT).strftime("%d/%m/%Y às %H:%M BRT")
            await self.send_message(
                f"✅ *ROP Odds System* — Conexão testada com sucesso!\n"
                f"Data/hora: {now}"
            )
            return True
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

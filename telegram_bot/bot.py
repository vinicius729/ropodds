"""Telegram Bot for sending odds alerts and reports."""

import asyncio
import logging

from telegram import Bot
from telegram.constants import ParseMode

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

# Telegram message limit
MAX_MESSAGE_LENGTH = 4096


class TelegramNotifier:
    """Sends messages to a Telegram group."""

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.bot: Bot | None = None

    def _ensure_bot(self):
        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN não configurado. "
                "Configure no arquivo .env ou passe como parâmetro."
            )
        if not self.chat_id:
            raise ValueError(
                "TELEGRAM_CHAT_ID não configurado. "
                "Configure no arquivo .env ou passe como parâmetro."
            )
        if not self.bot:
            self.bot = Bot(token=self.token)

    async def send_message(self, text: str, parse_mode: str = ParseMode.MARKDOWN) -> bool:
        """Send a text message to the configured group."""
        self._ensure_bot()

        try:
            # Split long messages
            chunks = self._split_message(text)

            for chunk in chunks:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    parse_mode=parse_mode,
                )
                if len(chunks) > 1:
                    await asyncio.sleep(1)  # Rate limiting

            logger.info(f"Telegram: Sent {len(chunks)} message(s)")
            return True

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            # Retry without markdown if parse error
            if "parse" in str(e).lower() or "markdown" in str(e).lower():
                try:
                    chunks = self._split_message(text)
                    for chunk in chunks:
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=chunk,
                        )
                    logger.info("Telegram: Sent without markdown formatting")
                    return True
                except Exception as e2:
                    logger.error(f"Telegram retry error: {e2}")
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
        current = ""

        # Split by separator lines
        sections = text.split("━━━━━━━━━━━━━━━━━━━━━━")

        for section in sections:
            candidate = current + ("━━━━━━━━━━━━━━━━━━━━━━" if current else "") + section

            if len(candidate) > MAX_MESSAGE_LENGTH:
                if current:
                    chunks.append(current)
                current = section
            else:
                current = candidate

        if current:
            chunks.append(current)

        # Handle case where a single section exceeds limit
        final = []
        for chunk in chunks:
            if len(chunk) <= MAX_MESSAGE_LENGTH:
                final.append(chunk)
            else:
                # Split by lines
                lines = chunk.split("\n")
                buf = ""
                for line in lines:
                    if len(buf) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                        final.append(buf)
                        buf = line
                    else:
                        buf = buf + "\n" + line if buf else line
                if buf:
                    final.append(buf)

        return final

    async def test_connection(self) -> bool:
        """Test the bot connection and send a test message."""
        self._ensure_bot()
        try:
            me = await self.bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")
            await self.send_message("✅ *ROP Odds System* — Conexão testada com sucesso!")
            return True
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

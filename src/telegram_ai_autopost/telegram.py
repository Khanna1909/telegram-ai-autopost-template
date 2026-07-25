from __future__ import annotations

from pathlib import Path

import requests


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(
        self, bot_token: str, channel_id: str, session: requests.Session | None = None
    ):
        self.channel_id = channel_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session = session or requests.Session()

    def check_connection(self) -> dict[str, str | int | bool]:
        bot_response = self.session.get(f"{self.base_url}/getMe", timeout=30)
        bot = self._result(bot_response)
        chat_response = self.session.get(
            f"{self.base_url}/getChat",
            params={"chat_id": self.channel_id},
            timeout=30,
        )
        chat = self._result(chat_response)
        return {
            "ok": True,
            "bot_id": int(bot["id"]),
            "bot_username": str(bot.get("username", "")),
            "chat_id": int(chat["id"]),
            "chat_title": str(chat.get("title", chat.get("username", ""))),
        }

    def send_photo(self, path: str | Path, caption: str = "") -> int:
        with Path(path).open("rb") as photo:
            response = self.session.post(
                f"{self.base_url}/sendPhoto",
                data={"chat_id": self.channel_id, "caption": caption[:1024]},
                files={"photo": photo},
                timeout=120,
            )
        return self._message_id(response)

    def send_text(self, text: str) -> list[int]:
        message_ids: list[int] = []
        for chunk in split_text(text, 4096):
            response = self.session.post(
                f"{self.base_url}/sendMessage",
                data={
                    "chat_id": self.channel_id,
                    "text": chunk,
                    "disable_web_page_preview": "true",
                },
                timeout=60,
            )
            message_ids.append(self._message_id(response))
        return message_ids

    @staticmethod
    def _message_id(response: requests.Response) -> int:
        return int(TelegramClient._result(response)["message_id"])

    @staticmethod
    def _result(response: requests.Response) -> dict:
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise TelegramError(payload.get("description") or "Telegram request failed")
        return payload["result"]


def split_text(text: str, limit: int) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks

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
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise TelegramError(payload.get("description") or "Telegram request failed")
        return int(payload["result"]["message_id"])


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


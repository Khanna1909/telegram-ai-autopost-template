from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VisualMode(StrEnum):
    CLEAN = "clean_visual"
    SIGNATURE = "signature_visual"
    EDUCATIONAL = "educational_card"


@dataclass(frozen=True)
class ContentExample:
    id: str
    mode: VisualMode
    title: str
    post_text: str
    visual_prompt: str
    card_text: str = ""


@dataclass
class ReleaseState:
    release_id: str
    example_id: str
    task_id: str = ""
    media_url: str = ""
    media_path: str = ""
    photo_sent: bool = False
    text_sent: bool = False
    published: bool = False


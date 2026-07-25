from __future__ import annotations

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .models import ContentExample, VisualMode

SLOT_INDEX = {"morning": 0, "day": 1, "evening": 2}


def load_examples(path: str | Path) -> list[ContentExample]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    examples = [
        ContentExample(
            id=item["id"],
            mode=VisualMode(item["mode"]),
            title=item["title"],
            post_text=item["post_text"],
            visual_prompt=item["visual_prompt"],
            card_text=item.get("card_text", ""),
        )
        for item in raw.get("examples", [])
    ]
    if len(examples) < 3:
        raise ValueError("Add at least three examples")
    return examples


def select_example(
    examples: list[ContentExample], local_date: date, slot: str
) -> ContentExample:
    if slot not in SLOT_INDEX:
        raise ValueError(f"Unknown slot: {slot}")
    ordinal = local_date.toordinal() * 3 + SLOT_INDEX[slot]
    return examples[ordinal % len(examples)]


def release_id(local_date: date, slot: str) -> str:
    if slot not in SLOT_INDEX:
        raise ValueError(f"Unknown slot: {slot}")
    return f"{local_date.isoformat()}-{slot}"


def timezone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


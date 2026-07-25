from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .config import live_mode
from .kie import KieClient
from .media import validate_image
from .models import ContentExample, ReleaseState
from .prompts import build_post_text, build_visual_prompt
from .state import StateStore
from .telegram import TelegramClient


def preview_release(
    config: dict[str, Any],
    example: ContentExample,
    release_id: str,
) -> dict[str, str]:
    return {
        "release_id": release_id,
        "example_id": example.id,
        "visual_mode": example.mode.value,
        "visual_prompt": build_visual_prompt(
            example, str(config["brand"]["signature"])
        ),
        "post_text": build_post_text(
            example, str(config["brand"].get("post_footer", ""))
        ),
    }


def run_release(
    *,
    config: dict[str, Any],
    store: StateStore,
    example: ContentExample,
    release_id: str,
    local_date: date,
    kie: KieClient | None = None,
    telegram: TelegramClient | None = None,
    media_dir: str | Path = "media",
) -> dict[str, str]:
    preview = preview_release(config, example, release_id)
    if not live_mode(config):
        return {**preview, "status": "dry-run"}

    if kie is None or telegram is None:
        raise ValueError("Live mode requires KIE and Telegram clients")

    state = store.get(release_id)
    if state and state.published:
        return {**preview, "status": "already-published"}
    if state is None:
        state = ReleaseState(release_id=release_id, example_id=example.id)
        store.save(state)

    generation = config["generation"]
    visual_prompt = preview["visual_prompt"]
    if not state.task_id and not state.media_url:
        day = local_date.isoformat()
        limit = int(generation.get("max_generations_per_day", 3))
        if store.generation_count(day) >= limit:
            raise RuntimeError(f"Daily generation limit of {limit} reached")
        state.task_id = kie.create_image_task(
            model=str(generation["model"]),
            prompt=visual_prompt,
            aspect_ratio=str(generation["aspect_ratio"]),
        )
        store.increment_generation_count(day)
        store.save(state)

    if not state.media_url:
        state.media_url = kie.wait_for_result(
            state.task_id,
            timeout_seconds=int(generation.get("poll_timeout_seconds", 900)),
        )
        store.save(state)

    media_path = (
        Path(state.media_path)
        if state.media_path
        else Path(media_dir) / f"{release_id}.jpg"
    )
    if not media_path.exists():
        kie.download(state.media_url, media_path)
        state.media_path = str(media_path)
        store.save(state)

    validate_image(
        media_path,
        min_width=int(generation.get("min_image_width", 512)),
        min_height=int(generation.get("min_image_height", 512)),
    )

    if not state.photo_sent:
        telegram.send_photo(
            media_path, str(config["brand"].get("image_intro", ""))
        )
        state.photo_sent = True
        store.save(state)

    if not state.text_sent:
        telegram.send_text(preview["post_text"])
        state.text_sent = True
        store.save(state)

    state.published = state.photo_sent and state.text_sent
    store.save(state)
    return {**preview, "status": "published"}


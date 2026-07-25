from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from telegram_ai_autopost.app import run_release
from telegram_ai_autopost.config import live_mode
from telegram_ai_autopost.content import release_id, select_example
from telegram_ai_autopost.media import InvalidMediaError, validate_image
from telegram_ai_autopost.models import ContentExample, ReleaseState, VisualMode
from telegram_ai_autopost.prompts import build_visual_prompt
from telegram_ai_autopost.state import StateStore
from telegram_ai_autopost.telegram import split_text


def config() -> dict:
    return {
        "brand": {
            "signature": "YOUR BRAND / YOUR NAME",
            "image_intro": "Prompt below",
            "post_footer": "",
        },
        "generation": {
            "model": "gpt-image-2-text-to-image",
            "aspect_ratio": "3:4",
            "api_base_url": "https://api.kie.ai",
            "poll_timeout_seconds": 10,
            "min_image_width": 512,
            "min_image_height": 512,
            "max_generations_per_day": 3,
        },
        "telegram": {"enabled": False, "channel_id": "@YOUR_CHANNEL"},
        "safety": {"dry_run": True, "require_explicit_live_flag": True},
        "content": {"timezone": "Europe/Moscow", "examples_file": "unused"},
    }


def example(mode: VisualMode = VisualMode.CLEAN) -> ContentExample:
    return ContentExample(
        id="sample",
        mode=mode,
        title="Title",
        post_text="Post",
        visual_prompt="A premium editorial image.",
        card_text="ТОЧНЫЙ ТЕКСТ" if mode == VisualMode.EDUCATIONAL else "",
    )


def make_image(path: Path, size: tuple[int, int] = (700, 900)) -> None:
    Image.new("RGB", size, (40, 80, 120)).save(path, "JPEG", quality=95)


class FakeKie:
    def __init__(self, image_source: Path):
        self.image_source = image_source
        self.created = 0
        self.waited = 0
        self.downloaded = 0

    def create_image_task(self, **_: str) -> str:
        self.created += 1
        return "task-1"

    def wait_for_result(self, task_id: str, timeout_seconds: int) -> str:
        assert task_id == "task-1"
        assert timeout_seconds > 0
        self.waited += 1
        return "https://example.test/image.jpg"

    def download(self, url: str, destination: Path) -> Path:
        assert url.startswith("https://")
        self.downloaded += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.image_source.read_bytes())
        return destination


class FakeTelegram:
    def __init__(self):
        self.photos = 0
        self.texts = 0

    def send_photo(self, path: Path, caption: str = "") -> int:
        assert path.exists()
        assert caption
        self.photos += 1
        return 1

    def send_text(self, text: str) -> list[int]:
        assert text
        self.texts += 1
        return [2]


def enable_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("ALLOW_LIVE_PUBLISH", "true")


def test_default_config_is_not_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("ALLOW_LIVE_PUBLISH", raising=False)
    assert live_mode(config()) is False


@pytest.mark.parametrize(
    ("dry_run", "telegram", "allow"),
    [
        ("true", "true", "true"),
        ("false", "false", "true"),
        ("false", "true", "false"),
    ],
)
def test_all_three_live_switches_are_required(
    monkeypatch: pytest.MonkeyPatch, dry_run: str, telegram: str, allow: str
) -> None:
    monkeypatch.setenv("DRY_RUN", dry_run)
    monkeypatch.setenv("TELEGRAM_ENABLED", telegram)
    monkeypatch.setenv("ALLOW_LIVE_PUBLISH", allow)
    assert live_mode(config()) is False


def test_clean_prompt_allows_only_signature() -> None:
    prompt = build_visual_prompt(example(), "YOUR BRAND / YOUR NAME")
    assert 'reading exactly "YOUR BRAND / YOUR NAME"' in prompt
    assert "Do not include any other text" in prompt


def test_signature_prompt_allows_only_signature() -> None:
    prompt = build_visual_prompt(
        example(VisualMode.SIGNATURE), "YOUR BRAND / YOUR NAME"
    )
    assert "Do not include any other text" in prompt


def test_educational_card_contains_exact_prepared_text() -> None:
    prompt = build_visual_prompt(
        example(VisualMode.EDUCATIONAL), "YOUR BRAND / YOUR NAME"
    )
    assert "ТОЧНЫЙ ТЕКСТ" in prompt
    assert "without adding facts" in prompt


def test_educational_card_requires_text() -> None:
    item = ContentExample(
        id="bad",
        mode=VisualMode.EDUCATIONAL,
        title="Bad",
        post_text="Bad",
        visual_prompt="Card",
    )
    with pytest.raises(ValueError):
        build_visual_prompt(item, "SIGNATURE")


def test_release_id_is_deterministic() -> None:
    assert release_id(date(2026, 7, 25), "morning") == "2026-07-25-morning"


def test_example_selection_is_deterministic() -> None:
    items = [example(), example(VisualMode.SIGNATURE), example(VisualMode.EDUCATIONAL)]
    assert select_example(items, date(2026, 7, 25), "day") == select_example(
        items, date(2026, 7, 25), "day"
    )


def test_empty_image_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "empty.jpg"
    path.touch()
    with pytest.raises(InvalidMediaError):
        validate_image(path)


def test_damaged_image_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"x" * 2048)
    with pytest.raises(InvalidMediaError):
        validate_image(path)


def test_small_dimensions_are_blocked(tmp_path: Path) -> None:
    path = tmp_path / "small.jpg"
    make_image(path, (200, 200))
    with pytest.raises(InvalidMediaError):
        validate_image(path)


def test_valid_image_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "good.jpg"
    make_image(path)
    assert validate_image(path) == (700, 900)


def test_long_telegram_text_is_split() -> None:
    chunks = split_text("word " * 3000, 4096)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)


def test_dry_run_does_not_create_state_or_call_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    store = StateStore(tmp_path / "state.json")
    result = run_release(
        config=config(),
        store=store,
        example=example(),
        release_id="2026-07-25-morning",
        local_date=date(2026, 7, 25),
    )
    assert result["status"] == "dry-run"
    assert store.get("2026-07-25-morning") is None


def test_live_run_generates_and_publishes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_live(monkeypatch)
    source = tmp_path / "source.jpg"
    make_image(source)
    kie = FakeKie(source)
    telegram = FakeTelegram()
    store = StateStore(tmp_path / "state.json")
    kwargs = dict(
        config=config(),
        store=store,
        example=example(),
        release_id="2026-07-25-morning",
        local_date=date(2026, 7, 25),
        kie=kie,
        telegram=telegram,
        media_dir=tmp_path / "media",
    )
    assert run_release(**kwargs)["status"] == "published"
    assert (kie.created, kie.waited, kie.downloaded) == (1, 1, 1)
    assert (telegram.photos, telegram.texts) == (1, 1)

    assert run_release(**kwargs)["status"] == "already-published"
    assert (kie.created, kie.waited, kie.downloaded) == (1, 1, 1)
    assert (telegram.photos, telegram.texts) == (1, 1)


def test_existing_task_is_reused_without_new_paid_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_live(monkeypatch)
    source = tmp_path / "source.jpg"
    make_image(source)
    kie = FakeKie(source)
    telegram = FakeTelegram()
    store = StateStore(tmp_path / "state.json")
    store.save(
        ReleaseState(
            release_id="2026-07-25-day", example_id="sample", task_id="task-1"
        )
    )
    run_release(
        config=config(),
        store=store,
        example=example(),
        release_id="2026-07-25-day",
        local_date=date(2026, 7, 25),
        kie=kie,
        telegram=telegram,
        media_dir=tmp_path / "media",
    )
    assert kie.created == 0
    assert kie.waited == 1


def test_completed_photo_is_not_sent_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_live(monkeypatch)
    source = tmp_path / "source.jpg"
    make_image(source)
    media = tmp_path / "media.jpg"
    make_image(media)
    kie = FakeKie(source)
    telegram = FakeTelegram()
    store = StateStore(tmp_path / "state.json")
    store.save(
        ReleaseState(
            release_id="2026-07-25-evening",
            example_id="sample",
            task_id="task-1",
            media_url="https://example.test/image.jpg",
            media_path=str(media),
            photo_sent=True,
        )
    )
    run_release(
        config=config(),
        store=store,
        example=example(),
        release_id="2026-07-25-evening",
        local_date=date(2026, 7, 25),
        kie=kie,
        telegram=telegram,
    )
    assert telegram.photos == 0
    assert telegram.texts == 1
    assert kie.created == 0


def test_daily_generation_limit_blocks_new_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_live(monkeypatch)
    source = tmp_path / "source.jpg"
    make_image(source)
    store = StateStore(tmp_path / "state.json")
    for _ in range(3):
        store.increment_generation_count("2026-07-25")
    kie = FakeKie(source)
    with pytest.raises(RuntimeError, match="Daily generation limit"):
        run_release(
            config=config(),
            store=store,
            example=example(),
            release_id="2026-07-25-morning",
            local_date=date(2026, 7, 25),
            kie=kie,
            telegram=FakeTelegram(),
            media_dir=tmp_path / "media",
        )
    assert kie.created == 0


def test_state_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.json")
    value = ReleaseState(release_id="release", example_id="example")
    store.save(value)
    assert store.get("release") == value


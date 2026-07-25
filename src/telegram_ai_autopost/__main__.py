from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .app import preview_release, run_release
from .config import load_config, live_mode, require_secret
from .content import load_examples, release_id, select_example, timezone
from .kie import KieClient
from .state import StateStore
from .telegram import TelegramClient


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Telegram AI autopost template")
    result.add_argument("--config", default="config/user_config.yaml")
    result.add_argument(
        "--operation", choices=("safe-check", "generate", "catch-up"), default="safe-check"
    )
    result.add_argument(
        "--slot", choices=("morning", "day", "evening"), default="morning"
    )
    result.add_argument("--state-file", default="state-data/state.json")
    result.add_argument("--output", default="")
    return result


def main() -> None:
    args = parser().parse_args()
    config = load_config(args.config)
    examples = load_examples(config["content"]["examples_file"])
    local_now = datetime.now(timezone(str(config["content"]["timezone"])))
    slots = ("morning", "day", "evening") if args.operation == "catch-up" else (args.slot,)
    store = StateStore(args.state_file)

    kie = telegram = None
    if live_mode(config):
        configured_channel = str(config["telegram"].get("channel_id", "")).strip()
        if not configured_channel or configured_channel == "@YOUR_CHANNEL":
            configured_channel = require_secret("TELEGRAM_CHANNEL_ID")
        kie = KieClient(
            api_key=require_secret("KIE_API_KEY"),
            base_url=str(config["generation"]["api_base_url"]),
        )
        telegram = TelegramClient(
            bot_token=require_secret("TELEGRAM_BOT_TOKEN"),
            channel_id=configured_channel,
        )

    results: list[dict[str, str]] = []
    for slot in slots:
        item = select_example(examples, local_now.date(), slot)
        rid = release_id(local_now.date(), slot)
        if args.operation == "safe-check":
            results.append({**preview_release(config, item, rid), "status": "safe-check"})
        else:
            results.append(
                run_release(
                    config=config,
                    store=store,
                    example=item,
                    release_id=rid,
                    local_date=local_now.date(),
                    kie=kie,
                    telegram=telegram,
                )
            )

    rendered = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

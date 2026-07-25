from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from .models import ReleaseState


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict:
        if not self.path.exists():
            return {"releases": {}, "daily_generation_counts": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, release_id: str) -> ReleaseState | None:
        raw = self._read_all()["releases"].get(release_id)
        return ReleaseState(**raw) if raw else None

    def save(self, state: ReleaseState) -> None:
        data = self._read_all()
        data["releases"][state.release_id] = asdict(state)
        self._write(data, f"Save {state.release_id}")

    def generation_count(self, day: str) -> int:
        return int(self._read_all()["daily_generation_counts"].get(day, 0))

    def increment_generation_count(self, day: str) -> None:
        data = self._read_all()
        counts = data["daily_generation_counts"]
        counts[day] = int(counts.get(day, 0)) + 1
        self._write(data, f"Count generation for {day}")

    def _write(self, data: dict, message: str) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if os.getenv("STATE_AUTO_PUSH", "").lower() not in {"1", "true", "yes"}:
            return
        repo_dir = self.path.parent
        subprocess.run(
            ["git", "add", self.path.name], cwd=repo_dir, check=True, capture_output=True
        )
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_dir,
            check=False,
            capture_output=True,
        )
        if diff.returncode == 0:
            return
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "state"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

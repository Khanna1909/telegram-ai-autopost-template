from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


class KieError(RuntimeError):
    pass


class KieClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.kie.ai",
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def check_connection(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/api/v1/chat/credit",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise KieError(
                f"KIE connection failed: {payload.get('msg', 'unknown error')}"
            )
        return {
            "ok": True,
            "credits": (payload.get("data") or {}).get("credit"),
        }

    def create_image_task(
        self, *, model: str, prompt: str, aspect_ratio: str
    ) -> str:
        response = self.session.post(
            f"{self.base_url}/api/v1/jobs/createTask",
            json={
                "model": model,
                "input": {"prompt": prompt, "aspect_ratio": aspect_ratio},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        task_id = str(payload.get("data", {}).get("taskId", "")).strip()
        if payload.get("code") != 200 or not task_id:
            raise KieError(f"KIE did not create a task: {payload.get('msg', 'unknown error')}")
        return task_id

    def wait_for_result(self, task_id: str, timeout_seconds: int = 900) -> str:
        deadline = time.monotonic() + timeout_seconds
        delay = 3.0
        while time.monotonic() < deadline:
            response = self.session.get(
                f"{self.base_url}/api/v1/jobs/recordInfo",
                params={"taskId": task_id},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or {}
            state = str(data.get("state", "")).lower()
            if state == "success":
                result = data.get("resultJson") or "{}"
                if isinstance(result, str):
                    result = json.loads(result)
                urls = result.get("resultUrls") or []
                if not urls:
                    raise KieError("KIE task succeeded without a result URL")
                return str(urls[0])
            if state == "fail":
                raise KieError(data.get("failMsg") or "KIE generation failed")
            time.sleep(delay)
            delay = min(delay * 1.5, 20.0)
        raise KieError(f"KIE task {task_id} timed out")

    def download(self, url: str, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=128 * 1024):
                    if chunk:
                        output.write(chunk)
        return path

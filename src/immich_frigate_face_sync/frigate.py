from __future__ import annotations

from typing import Any, cast

import httpx

from .http import with_retries


class FrigateClient:
    def __init__(self, base_url: str, api_key: str | None, timeout: float) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.Client(
            base_url=f"{base_url}/api", headers=headers, timeout=timeout, follow_redirects=True
        )

    def close(self) -> None:
        self.client.close()

    def faces(self) -> dict[str, list[str]]:
        def run() -> dict[str, list[str]]:
            response = self.client.get("/faces")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Frigate /faces did not return an object")
            return {str(key): list(value) for key, value in data.items()}

        return with_retries(run, "Frigate GET /faces")

    def register_face(self, name: str, image: bytes, filename: str) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            files = {"file": (filename, image, "image/jpeg")}
            response = self.client.post(f"/faces/{name}/register", files=files)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        return with_retries(run, f"Frigate register {name}", attempts=2)

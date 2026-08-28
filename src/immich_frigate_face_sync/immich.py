from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from .http import with_retries
from .models import Asset, Face, Person

LOGGER = logging.getLogger(__name__)


class ImmichClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url
        self.client = httpx.Client(
            base_url=f"{base_url}/api",
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        def run() -> Any:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            return response.json()

        return with_retries(run, f"Immich GET {path}")

    def _post(self, path: str, json: dict[str, Any]) -> Any:
        def run() -> Any:
            response = self.client.post(path, json=json)
            response.raise_for_status()
            return response.json()

        return with_retries(run, f"Immich POST {path}")

    def check(self) -> None:
        self._get("/people", {"page": 1, "size": 1})

    def people(self) -> list[Person]:
        out: list[Person] = []
        page = 1
        while True:
            data = self._get("/people", {"page": page, "size": 500, "withHidden": "true"})
            rows = data.get("people", []) if isinstance(data, dict) else []
            for item in rows:
                out.append(
                    Person(
                        id=item["id"],
                        name=item.get("name") or "",
                        is_hidden=bool(item.get("isHidden", False)),
                        is_favorite=bool(item.get("isFavorite", False)),
                        updated_at=item.get("updatedAt"),
                    )
                )
            if not data.get("hasNextPage"):
                return out
            page += 1

    def assets_for_person(self, person_id: str, limit: int) -> list[Asset]:
        assets, should_retry = self._assets_for_person_current(person_id, limit)
        if assets or not should_retry:
            return assets
        LOGGER.info(
            "Immich metadata search returned no verified assets for person; "
            "retrying legacy personIds compatibility path"
        )
        return self._assets_for_person_legacy(person_id, limit)

    def _assets_for_person_current(self, person_id: str, limit: int) -> tuple[list[Asset], bool]:
        out: list[Asset] = []
        saw_unverified_items = False
        cursor: str | None = None
        while len(out) < limit:
            body: dict[str, Any] = {
                "filter": {
                    "personIds": {"any": [person_id]},
                    "type": {"eq": "IMAGE"},
                    "visibility": {"eq": "timeline"},
                },
                "withPeople": True,
                "withExif": True,
                "size": min(100, limit - len(out)),
            }
            if cursor:
                body["cursor"] = cursor
            data = self._post("/search/metadata", body)
            assets = data.get("assets", {})
            for item in assets.get("items", []):
                if _asset_has_person(item, person_id):
                    out.append(_asset_from_item(item))
                else:
                    saw_unverified_items = True
            cursor = assets.get("nextCursor")
            if not cursor:
                return out, saw_unverified_items
        return out, saw_unverified_items

    def _assets_for_person_legacy(self, person_id: str, limit: int) -> list[Asset]:
        out: list[Asset] = []
        page = 1
        while len(out) < limit:
            body: dict[str, Any] = {
                "personIds": [person_id],
                "type": "IMAGE",
                "withPeople": True,
                "withExif": True,
                "page": page,
                "size": min(100, limit - len(out)),
            }
            data = self._post("/search/metadata", body)
            assets = data.get("assets", {})
            for item in assets.get("items", []):
                if item.get("type") == "IMAGE" and _asset_has_person(item, person_id):
                    out.append(_asset_from_item(item))
            if not assets.get("nextPage"):
                return out
            page += 1
        return out

    def faces_for_asset(self, asset_id: str) -> list[Face]:
        data = self._get("/faces", {"id": asset_id})
        faces: list[Face] = []
        for item in data:
            person = item.get("person")
            faces.append(
                Face(
                    id=item["id"],
                    asset_id=asset_id,
                    person_id=person.get("id") if person else None,
                    x1=item["boundingBoxX1"],
                    y1=item["boundingBoxY1"],
                    x2=item["boundingBoxX2"],
                    y2=item["boundingBoxY2"],
                    image_width=item["imageWidth"],
                    image_height=item["imageHeight"],
                )
            )
        return faces

    def original_asset(self, asset_id: str) -> bytes:
        def run() -> bytes:
            response = self.client.get(f"/assets/{asset_id}/original")
            response.raise_for_status()
            return response.content

        return with_retries(run, f"Immich asset {asset_id}")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _asset_has_person(item: dict[str, Any], person_id: str) -> bool:
    people = item.get("people")
    return isinstance(people, list) and any(person.get("id") == person_id for person in people)


def _asset_from_item(item: dict[str, Any]) -> Asset:
    return Asset(
        id=item["id"],
        width=item.get("width"),
        height=item.get("height"),
        taken_at=_parse_dt(item.get("localDateTime") or item.get("fileCreatedAt")),
    )

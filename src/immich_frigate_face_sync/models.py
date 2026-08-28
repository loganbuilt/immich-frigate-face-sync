from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    is_hidden: bool
    is_favorite: bool
    updated_at: str | None = None

    @property
    def eligible_name(self) -> str:
        return self.name.strip()


@dataclass(frozen=True)
class Asset:
    id: str
    width: int | None
    height: int | None
    taken_at: datetime | None


@dataclass(frozen=True)
class Face:
    id: str
    asset_id: str
    person_id: str | None
    x1: int
    y1: int
    x2: int
    y2: int
    image_width: int
    image_height: int


@dataclass(frozen=True)
class Candidate:
    person_id: str
    asset_id: str
    face_id: str
    score: float
    taken_at: datetime | None
    box_area: int


@dataclass(frozen=True)
class CropResult:
    image_bytes: bytes
    content_hash: str
    width: int
    height: int

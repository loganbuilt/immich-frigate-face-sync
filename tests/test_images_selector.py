from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

from PIL import Image

from immich_frigate_face_sync.images import crop_face, valid_face_box
from immich_frigate_face_sync.models import Asset, Candidate, Face
from immich_frigate_face_sync.naming import sanitize_frigate_name, unique_frigate_name
from immich_frigate_face_sync.selector import candidate_for, select_candidates


def face(**overrides: object) -> Face:
    data = {
        "id": "face1",
        "asset_id": "asset1",
        "person_id": "person1",
        "x1": 100,
        "y1": 100,
        "x2": 220,
        "y2": 240,
        "image_width": 400,
        "image_height": 400,
    }
    data.update(overrides)
    return Face(**data)  # type: ignore[arg-type]


def jpeg(width: int = 800, height: int = 800) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), (120, 80, 60)).save(output, format="JPEG")
    return output.getvalue()


def test_valid_face_box_rejects_bad_boxes() -> None:
    assert valid_face_box(face())
    assert not valid_face_box(face(x2=80))
    assert not valid_face_box(face(x2=120))
    assert not valid_face_box(face(x2=400, y2=120))


def test_crop_scales_and_pads() -> None:
    result = crop_face(jpeg(), face())
    assert result.width > 200
    assert result.height > 200
    assert len(result.content_hash) == 64


def test_candidate_matching_and_ranking() -> None:
    asset = Asset("asset1", 400, 400, datetime(2026, 1, 1, tzinfo=UTC))
    assert candidate_for(asset, face(person_id="other"), "person1") is None
    candidate = candidate_for(asset, face(), "person1")
    assert candidate is not None
    choices = select_candidates(
        [
            Candidate("p", "a1", "f1", 10, None, 10),
            Candidate("p", "a2", "f2", 30, None, 30),
            Candidate("p", "a2", "f3", 20, None, 20),
        ],
        2,
    )
    assert [item.face_id for item in choices] == ["f2", "f1"]


def test_identity_sanitization_and_duplicate_names() -> None:
    assert sanitize_frigate_name(" John Smith ") == "John Smith"
    assert sanitize_frigate_name("***") == "Immich Person"
    assert (
        unique_frigate_name("John Smith", "abcdef12-0000-4000-8000-000000000000", {"John Smith"})
        == "John Smith abcdef12"
    )

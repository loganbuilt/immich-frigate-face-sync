from __future__ import annotations

from .images import valid_face_box
from .models import Asset, Candidate, Face


def candidate_for(asset: Asset, face: Face, person_id: str) -> Candidate | None:
    if face.person_id != person_id or not valid_face_box(face):
        return None
    face_width = face.x2 - face.x1
    face_height = face.y2 - face.y1
    area = face_width * face_height
    source_area = (asset.width or face.image_width) * (asset.height or face.image_height)
    edge_penalty = 0.0
    margin = min(face.x1, face.y1, face.image_width - face.x2, face.image_height - face.y2)
    if margin < min(face_width, face_height) * 0.05:
        edge_penalty = area * 0.25
    score = min(area, 250_000) + min(source_area / 100, 50_000) - edge_penalty
    return Candidate(person_id, asset.id, face.id, float(score), asset.taken_at, area)


def select_candidates(candidates: list[Candidate], limit: int) -> list[Candidate]:
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            item.score,
            item.taken_at.timestamp() if item.taken_at else 0,
            item.face_id,
        ),
        reverse=True,
    )
    selected: list[Candidate] = []
    seen_assets: set[str] = set()
    for candidate in sorted_candidates:
        if candidate.asset_id in seen_assets:
            continue
        selected.append(candidate)
        seen_assets.add(candidate.asset_id)
        if len(selected) == limit:
            return selected
    for candidate in sorted_candidates:
        if candidate not in selected:
            selected.append(candidate)
            if len(selected) == limit:
                break
    return selected

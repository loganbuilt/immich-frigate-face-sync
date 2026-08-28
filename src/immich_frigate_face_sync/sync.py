from __future__ import annotations

import logging

from .config import Settings
from .frigate import FrigateClient
from .images import crop_face
from .immich import ImmichClient
from .models import Person
from .naming import unique_frigate_name
from .selector import candidate_for, select_candidates
from .state import StateStore

LOGGER = logging.getLogger(__name__)


class SyncEngine:
    def __init__(
        self, settings: Settings, immich: ImmichClient, frigate: FrigateClient, state: StateStore
    ) -> None:
        self.settings = settings
        self.immich = immich
        self.frigate = frigate
        self.state = state

    def sync_once(self) -> dict[str, int]:
        people = self.immich.people()
        LOGGER.info("Found %s Immich people", len(people))
        eligible = [person for person in people if self._eligible(person)]
        LOGGER.info(
            "Found %s eligible people using mode=%s", len(eligible), self.settings.people_mode
        )
        frigate_faces = self.frigate.faces()
        known_names = set(frigate_faces) | {person.frigate_name for person in self.state.people()}
        stats = {"people": len(eligible), "added_faces": 0, "skipped": 0, "errors": 0}

        for person in people:
            if not self._eligible(person):
                previous = self.state.get_person(person.id)
                if previous:
                    self.state.mark_seen_inactive(person.id, person.name)
                continue

            try:
                previous = self.state.get_person(person.id)
                if previous:
                    frigate_name = previous.frigate_name
                    if previous.immich_name != person.name:
                        LOGGER.info(
                            "%s: Immich name changed to %r; retaining Frigate identity %r",
                            previous.frigate_name,
                            person.name,
                            frigate_name,
                        )
                else:
                    frigate_name = unique_frigate_name(person.name, person.id, known_names)
                    known_names.add(frigate_name)
                self.state.upsert_person(person.id, person.name, frigate_name, True)
                added = self._sync_person(person, frigate_name)
                stats["added_faces"] += added
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("%s: sync failed: %s", person.name or person.id, exc)
                stats["errors"] += 1
        LOGGER.info(
            "Sync complete: people=%s added_faces=%s skipped=%s errors=%s",
            stats["people"],
            stats["added_faces"],
            stats["skipped"],
            stats["errors"],
        )
        return stats

    def _eligible(self, person: Person) -> bool:
        if not person.eligible_name or person.is_hidden:
            return False
        return self.settings.people_mode == "all" or person.is_favorite

    def _sync_person(self, person: Person, frigate_name: str) -> int:
        synced_count = self.state.synced_count(person.id)
        needed = max(0, self.settings.faces_per_person - synced_count)
        if needed == 0:
            LOGGER.info(
                "%s: %s/%s training samples already synchronized",
                frigate_name,
                synced_count,
                self.settings.faces_per_person,
            )
            self.state.mark_person_synced(person.id)
            return 0

        assets = self.immich.assets_for_person(person.id, self.settings.max_assets_per_person)
        candidates = []
        for asset in assets:
            for face in self.immich.faces_for_asset(asset.id):
                candidate = candidate_for(asset, face, person.id)
                if candidate:
                    candidates.append(candidate)
        already = self.state.synced_face_ids(person.id)
        choices = select_candidates(
            [item for item in candidates if item.face_id not in already], needed
        )
        LOGGER.info(
            "%s: found %s candidate faces, enrolling up to %s",
            frigate_name,
            len(choices),
            needed,
        )
        if self.settings.dry_run:
            LOGGER.info("%s: dry-run would enroll %s faces", frigate_name, len(choices))
            return 0

        added = 0
        for candidate in choices:
            try:
                image = self.immich.original_asset(candidate.asset_id)
                face = next(
                    face
                    for face in self.immich.faces_for_asset(candidate.asset_id)
                    if face.id == candidate.face_id
                )
                crop = crop_face(image, face)
                if self.state.has_content_hash(crop.content_hash):
                    continue
                result = self.frigate.register_face(
                    frigate_name, crop.image_bytes, f"{candidate.face_id}.jpg"
                )
                if result.get("success") is False:
                    raise RuntimeError(str(result.get("message", "Frigate rejected image")))
                self.state.record_face(
                    face_id=candidate.face_id,
                    person_id=person.id,
                    asset_id=candidate.asset_id,
                    content_hash=crop.content_hash,
                    frigate_name=frigate_name,
                    quality_score=candidate.score,
                )
                added += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "%s: skipped face %s from asset %s: %s",
                    frigate_name,
                    candidate.face_id,
                    candidate.asset_id,
                    exc,
                )
        self.state.mark_person_synced(person.id)
        LOGGER.info("%s: enrolled %s faces", frigate_name, added)
        return added

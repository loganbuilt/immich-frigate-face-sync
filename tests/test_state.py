from __future__ import annotations

from immich_frigate_face_sync.state import StateStore


def test_state_idempotency_and_unfavorite(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = StateStore(tmp_path / "state.sqlite3")
    store.upsert_person("p1", "Logan", "Logan", True)
    store.record_face(
        face_id="f1",
        person_id="p1",
        asset_id="a1",
        content_hash="hash1",
        frigate_name="Logan",
        quality_score=10.0,
    )
    store.record_face(
        face_id="f1",
        person_id="p1",
        asset_id="a1",
        content_hash="hash1",
        frigate_name="Logan",
        quality_score=10.0,
    )
    assert store.synced_count("p1") == 1
    assert store.has_content_hash("hash1")
    store.mark_seen_inactive("p1", "Logan")
    assert store.get_person("p1").active is False  # type: ignore[union-attr]
    store.close()

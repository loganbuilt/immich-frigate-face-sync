from __future__ import annotations

from immich_frigate_face_sync.health import HealthState


def test_health_records_failed_sync_without_success() -> None:
    health = HealthState()
    health.mark_sync(False, "ok", "error", "sync errors=7")
    payload = health.payload()
    assert payload["last_sync"] is not None
    assert payload["last_success"] is None
    assert payload["frigate"] == "error"
    assert payload["last_error"] == "sync errors=7"

from __future__ import annotations

from io import BytesIO

from PIL import Image
from pytest_httpx import HTTPXMock

from immich_frigate_face_sync.config import Settings
from immich_frigate_face_sync.frigate import FrigateClient
from immich_frigate_face_sync.immich import ImmichClient
from immich_frigate_face_sync.state import StateStore
from immich_frigate_face_sync.sync import SyncEngine


def settings(tmp_path, *, dry_run: bool = False) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        immich_url="http://immich",
        immich_api_key="secret",
        frigate_url="http://frigate",
        frigate_api_key=None,
        sync_interval_seconds=86400,
        faces_per_person=1,
        people_mode="favorites",
        data_dir=tmp_path,
        log_level="INFO",
        dry_run=dry_run,
        run_once=True,
        health_host="127.0.0.1",
        health_port=8080,
        request_timeout_seconds=10,
        max_assets_per_person=10,
    )


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 800), (100, 80, 70)).save(output, format="JPEG")
    return output.getvalue()


def add_immich_flow(
    httpx_mock: HTTPXMock,
    *,
    favorite: bool = True,
    person_id: str = "p1",
    include_downloads: bool = True,
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="http://immich/api/people?page=1&size=500&withHidden=true",
        json={
            "people": [
                {
                    "id": person_id,
                    "name": "John Smith",
                    "isHidden": False,
                    "isFavorite": favorite,
                    "thumbnailPath": "",
                }
            ],
            "hasNextPage": False,
        },
    )
    if favorite:
        httpx_mock.add_response(
            method="POST",
            url="http://immich/api/search/metadata",
            json={
                "assets": {
                    "items": [
                        {
                            "id": "a1",
                            "type": "IMAGE",
                            "width": 400,
                            "height": 400,
                            "localDateTime": "2026-01-01T00:00:00Z",
                            "people": [{"id": person_id}],
                        }
                    ],
                    "nextCursor": None,
                }
            },
        )
        face_json = [
            {
                "id": "f1",
                "boundingBoxX1": 100,
                "boundingBoxY1": 100,
                "boundingBoxX2": 240,
                "boundingBoxY2": 260,
                "imageWidth": 400,
                "imageHeight": 400,
                "person": {
                    "id": person_id,
                    "name": "John Smith",
                    "isHidden": False,
                    "thumbnailPath": "",
                },
            }
        ]
        httpx_mock.add_response(method="GET", url="http://immich/api/faces?id=a1", json=face_json)
        if include_downloads:
            httpx_mock.add_response(
                method="GET", url="http://immich/api/assets/a1/original", content=image_bytes()
            )
            httpx_mock.add_response(
                method="GET", url="http://immich/api/faces?id=a1", json=face_json
            )


def test_immich_people_pagination(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="http://immich/api/people?page=1&size=500&withHidden=true",
        json={
            "people": [
                {
                    "id": "p1",
                    "name": "A",
                    "isHidden": False,
                    "isFavorite": True,
                    "thumbnailPath": "",
                }
            ],
            "hasNextPage": True,
        },
    )
    httpx_mock.add_response(
        method="GET",
        url="http://immich/api/people?page=2&size=500&withHidden=true",
        json={
            "people": [
                {
                    "id": "p2",
                    "name": "B",
                    "isHidden": False,
                    "isFavorite": False,
                    "thumbnailPath": "",
                }
            ],
            "hasNextPage": False,
        },
    )
    client = ImmichClient("http://immich", "secret", 10)
    assert [person.id for person in client.people()] == ["p1", "p2"]


def test_metadata_search_pagination(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://immich/api/search/metadata",
        json={
            "assets": {
                "items": [{"id": "a1", "people": [{"id": "p1"}]}],
                "nextCursor": "c1",
            }
        },
    )
    httpx_mock.add_response(
        method="POST",
        url="http://immich/api/search/metadata",
        json={
            "assets": {
                "items": [{"id": "a2", "people": [{"id": "p1"}]}],
                "nextCursor": None,
            }
        },
    )
    client = ImmichClient("http://immich", "secret", 10)
    assert [asset.id for asset in client.assets_for_person("p1", 10)] == ["a1", "a2"]


def test_metadata_search_falls_back_when_current_filter_is_ignored(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://immich/api/search/metadata",
        json={
            "assets": {
                "items": [{"id": "wrong", "type": "VIDEO", "people": []}],
                "nextCursor": None,
            }
        },
    )
    httpx_mock.add_response(
        method="POST",
        url="http://immich/api/search/metadata",
        json={
            "assets": {
                "items": [{"id": "a1", "type": "IMAGE", "people": [{"id": "p1"}]}],
                "nextPage": None,
            }
        },
    )
    client = ImmichClient("http://immich", "secret", 10)
    assert [asset.id for asset in client.assets_for_person("p1", 10)] == ["a1"]


def test_favorite_enrollment_and_restart_idempotency(tmp_path, httpx_mock: HTTPXMock) -> None:  # type: ignore[no-untyped-def]
    cfg = settings(tmp_path)
    add_immich_flow(httpx_mock)
    httpx_mock.add_response(method="GET", url="http://frigate/api/faces", json={})
    httpx_mock.add_response(
        method="POST",
        url="http://frigate/api/faces/John%20Smith/register",
        json={"success": True, "message": "ok"},
    )
    store = StateStore(cfg.db_path)
    engine = SyncEngine(
        cfg,
        ImmichClient("http://immich", "secret", 10),
        FrigateClient("http://frigate", None, 10),
        store,
    )
    stats = engine.sync_once()
    assert stats["added_faces"] == 1
    assert store.synced_count("p1") == 1
    store.close()


def test_dry_run_performs_no_frigate_writes(tmp_path, httpx_mock: HTTPXMock) -> None:  # type: ignore[no-untyped-def]
    cfg = settings(tmp_path, dry_run=True)
    add_immich_flow(httpx_mock, include_downloads=False)
    httpx_mock.add_response(method="GET", url="http://frigate/api/faces", json={})
    store = StateStore(cfg.db_path)
    engine = SyncEngine(
        cfg,
        ImmichClient("http://immich", "secret", 10),
        FrigateClient("http://frigate", None, 10),
        store,
    )
    engine.sync_once()
    assert store.synced_count("p1") == 0


def test_unfavorite_no_delete(tmp_path, httpx_mock: HTTPXMock) -> None:  # type: ignore[no-untyped-def]
    cfg = settings(tmp_path)
    store = StateStore(cfg.db_path)
    store.upsert_person("p1", "John Smith", "John Smith", True)
    add_immich_flow(httpx_mock, favorite=False)
    httpx_mock.add_response(
        method="GET", url="http://frigate/api/faces", json={"John Smith": ["old.jpg"]}
    )
    engine = SyncEngine(
        cfg,
        ImmichClient("http://immich", "secret", 10),
        FrigateClient("http://frigate", None, 10),
        store,
    )
    engine.sync_once()
    assert store.get_person("p1").active is False  # type: ignore[union-attr]


def test_frigate_rejection_is_person_error(tmp_path, httpx_mock: HTTPXMock) -> None:  # type: ignore[no-untyped-def]
    cfg = settings(tmp_path)
    add_immich_flow(httpx_mock)
    httpx_mock.add_response(method="GET", url="http://frigate/api/faces", json={})
    httpx_mock.add_response(
        method="POST",
        url="http://frigate/api/faces/John%20Smith/register",
        json={"success": False, "message": "bad"},
    )
    store = StateStore(cfg.db_path)
    engine = SyncEngine(
        cfg,
        ImmichClient("http://immich", "secret", 10),
        FrigateClient("http://frigate", None, 10),
        store,
    )
    stats = engine.sync_once()
    assert stats["errors"] == 0
    assert store.synced_count("p1") == 0


def test_same_name_people_get_distinct_frigate_names(tmp_path, httpx_mock: HTTPXMock) -> None:  # type: ignore[no-untyped-def]
    cfg = settings(tmp_path, dry_run=True)
    httpx_mock.add_response(
        method="GET",
        url="http://immich/api/people?page=1&size=500&withHidden=true",
        json={
            "people": [
                {
                    "id": "abcdef12-0000-4000-8000-000000000000",
                    "name": "John Smith",
                    "isHidden": False,
                    "isFavorite": True,
                    "thumbnailPath": "",
                },
                {
                    "id": "abcdef13-0000-4000-8000-000000000000",
                    "name": "John Smith",
                    "isHidden": False,
                    "isFavorite": True,
                    "thumbnailPath": "",
                },
            ],
            "hasNextPage": False,
        },
    )
    for _pid in ["abcdef12-0000-4000-8000-000000000000", "abcdef13-0000-4000-8000-000000000000"]:
        httpx_mock.add_response(
            method="POST",
            url="http://immich/api/search/metadata",
            json={"assets": {"items": [], "nextCursor": None}},
        )
    httpx_mock.add_response(method="GET", url="http://frigate/api/faces", json={})
    store = StateStore(cfg.db_path)
    engine = SyncEngine(
        cfg,
        ImmichClient("http://immich", "secret", 10),
        FrigateClient("http://frigate", None, 10),
        store,
    )
    engine.sync_once()
    names = sorted(person.frigate_name for person in store.people())
    assert names == ["John Smith", "John Smith abcdef13"]

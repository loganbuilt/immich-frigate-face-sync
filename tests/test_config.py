from __future__ import annotations

import pytest

from immich_frigate_face_sync.config import (
    ConfigError,
    normalize_url,
    parse_bool,
    parse_duration_seconds,
)


def test_normalize_url_removes_trailing_api() -> None:
    assert normalize_url("http://immich:2283/api/") == "http://immich:2283"
    assert normalize_url("https://frigate.local/base/api") == "https://frigate.local/base"


def test_duration_parsing() -> None:
    assert parse_duration_seconds("24h") == 86400
    assert parse_duration_seconds("5m") == 300
    with pytest.raises(ConfigError):
        parse_duration_seconds("soon")


def test_bool_parsing() -> None:
    assert parse_bool("true") is True
    assert parse_bool("0") is False
    with pytest.raises(ConfigError):
        parse_bool("maybe")

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class ConfigError(ValueError):
    pass


def _secret(name: str) -> str | None:
    value = os.getenv(name)
    file_value = os.getenv(f"{name}_FILE")
    if value and file_value:
        raise ConfigError(f"Set only one of {name} or {name}_FILE")
    if file_value:
        try:
            return Path(file_value).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigError(f"Unable to read {name}_FILE: {exc}") from exc
    return value


def normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ConfigError("URL cannot be empty")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"Invalid URL: {value}")
    path = re.sub(r"(/api)+$", "", parsed.path.rstrip("/"))
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value}")


def parse_duration_seconds(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+)\s*([smhd]?)\s*", value)
    if not match:
        raise ConfigError("Duration must be an integer with optional suffix s, m, h, or d")
    amount = int(match.group(1))
    unit = match.group(2) or "s"
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    seconds = amount * multiplier
    if seconds <= 0:
        raise ConfigError("Duration must be positive")
    return seconds


@dataclass(frozen=True)
class Settings:
    immich_url: str
    immich_api_key: str
    frigate_url: str
    frigate_api_key: str | None
    sync_interval_seconds: int
    faces_per_person: int
    people_mode: str
    data_dir: Path
    log_level: str
    dry_run: bool
    run_once: bool
    health_host: str
    health_port: int
    request_timeout_seconds: float
    max_assets_per_person: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.sqlite3"


def load_settings() -> Settings:
    immich_url = os.getenv("IMMICH_URL")
    frigate_url = os.getenv("FRIGATE_URL")
    immich_api_key = _secret("IMMICH_API_KEY")
    if not immich_url:
        raise ConfigError("IMMICH_URL is required")
    if not frigate_url:
        raise ConfigError("FRIGATE_URL is required")
    if not immich_api_key:
        raise ConfigError("IMMICH_API_KEY is required")
    faces_per_person = int(os.getenv("FACES_PER_PERSON", "10"))
    if not 1 <= faces_per_person <= 50:
        raise ConfigError("FACES_PER_PERSON must be between 1 and 50")
    people_mode = os.getenv("PEOPLE_MODE", "favorites").strip().lower()
    if people_mode not in {"favorites", "all"}:
        raise ConfigError("PEOPLE_MODE must be favorites or all")
    return Settings(
        immich_url=normalize_url(immich_url),
        immich_api_key=immich_api_key,
        frigate_url=normalize_url(frigate_url),
        frigate_api_key=_secret("FRIGATE_API_KEY"),
        sync_interval_seconds=parse_duration_seconds(os.getenv("SYNC_INTERVAL", "24h")),
        faces_per_person=faces_per_person,
        people_mode=people_mode,
        data_dir=Path(os.getenv("DATA_DIR", "/data")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        dry_run=parse_bool(os.getenv("DRY_RUN"), False),
        run_once=parse_bool(os.getenv("RUN_ONCE"), False),
        health_host=os.getenv("HEALTH_HOST", "0.0.0.0"),
        health_port=int(os.getenv("HEALTH_PORT", "8080")),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT", "30")),
        max_assets_per_person=int(os.getenv("MAX_ASSETS_PER_PERSON", "500")),
    )

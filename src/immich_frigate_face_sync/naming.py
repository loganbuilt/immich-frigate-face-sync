from __future__ import annotations

import re


def sanitize_frigate_name(name: str) -> str:
    value = re.sub(r"\s+", " ", name.strip())
    value = re.sub(r"[^A-Za-z0-9 _.-]", "", value)
    value = value.replace("/", "_").replace("\\", "_")
    value = value.strip(" ._-")
    if not value:
        value = "Immich Person"
    return value[:80]


def unique_frigate_name(display_name: str, person_id: str, existing: set[str]) -> str:
    base = sanitize_frigate_name(display_name)
    if base not in existing:
        return base
    suffix = person_id.replace("-", "")[:8]
    candidate = f"{base} {suffix}"
    counter = 2
    while candidate in existing:
        candidate = f"{base} {suffix}-{counter}"
        counter += 1
    return candidate

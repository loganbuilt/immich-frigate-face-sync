from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

LOGGER = logging.getLogger(__name__)


def with_retries[T](operation: Callable[[], T], label: str, attempts: int = 3) -> T:
    delay = 0.5
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise
            last = exc
        if attempt < attempts:
            LOGGER.debug("%s failed on attempt %s; retrying", label, attempt)
            time.sleep(delay)
            delay *= 2
    assert last is not None
    raise last

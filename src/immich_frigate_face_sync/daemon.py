from __future__ import annotations

import logging
import signal
import time

from .config import Settings
from .frigate import FrigateClient
from .health import HealthState, start_health_server
from .immich import ImmichClient
from .state import StateStore
from .sync import SyncEngine

LOGGER = logging.getLogger(__name__)


def run(settings: Settings) -> int:
    stop = False

    def _stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    health = HealthState(config_valid=True)
    server = start_health_server(health, settings.health_host, settings.health_port)
    state = StateStore(settings.db_path)
    immich = ImmichClient(
        settings.immich_url, settings.immich_api_key, settings.request_timeout_seconds
    )
    frigate = FrigateClient(
        settings.frigate_url, settings.frigate_api_key, settings.request_timeout_seconds
    )
    engine = SyncEngine(settings, immich, frigate, state)
    try:
        while not stop:
            try:
                stats = engine.sync_once()
                if stats["errors"]:
                    health.mark_sync(False, "ok", "error", f"sync errors={stats['errors']}")
                else:
                    health.mark_sync(True, "ok", "ok")
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Sync cycle failed: %s", exc)
                health.mark_sync(False, "error", "error", str(exc))
                if settings.run_once:
                    return 1
            if settings.run_once:
                return 0
            LOGGER.info("Next sync in %ss", settings.sync_interval_seconds)
            deadline = time.monotonic() + settings.sync_interval_seconds
            while not stop and time.monotonic() < deadline:
                time.sleep(min(1.0, deadline - time.monotonic()))
        return 0
    finally:
        server.shutdown()
        immich.close()
        frigate.close()
        state.close()

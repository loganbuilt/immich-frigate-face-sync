from __future__ import annotations

import logging
import sys

from .config import ConfigError, load_settings
from .daemon import run


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        logging.error("Invalid configuration: %s", exc)
        return 2
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())

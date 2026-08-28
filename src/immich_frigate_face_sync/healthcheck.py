from __future__ import annotations

import json
import os
import sys
from urllib.request import urlopen


def main() -> int:
    port = os.getenv("HEALTH_PORT", "8080")
    with urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:  # noqa: S310
        payload = json.loads(response.read().decode())
    return 0 if payload.get("status") == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())

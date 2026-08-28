from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class HealthState:
    config_valid: bool = True
    last_sync: str | None = None
    last_success: str | None = None
    immich: str = "unknown"
    frigate: str = "unknown"
    last_error: str | None = None

    def mark_sync(self, success: bool, immich: str, frigate: str, error: str | None = None) -> None:
        stamp = datetime.now(UTC).isoformat()
        self.last_sync = stamp
        if success:
            self.last_success = stamp
        self.immich = immich
        self.frigate = frigate
        self.last_error = error

    def payload(self) -> dict[str, object]:
        status = "healthy" if self.config_valid else "unhealthy"
        data = asdict(self)
        data["status"] = status
        return data


def start_health_server(state: HealthState, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(state.payload()).encode()
            self.send_response(200 if state.config_valid else 500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

from http.server import BaseHTTPRequestHandler
import json
import threading

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class Handler(BaseHTTPRequestHandler):
    def _send_response(self, response):
        if response is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        if self.path.startswith("/api/") or self.path == "/health":
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response.body)

    def do_GET(self):
        self._send_response(dispatch_get(self.path))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1_048_576:
                raise ValueError("Corpo da solicitação muito grande.")
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            response = RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode())
        else:
            response = dispatch_post(self.path, payload)
        self._send_response(response)
        if response is not None and self.path == "/api/shutdown":
            # Shutdown must run outside the serving thread.
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        print(f"[central-v2] {format % args}", flush=True)

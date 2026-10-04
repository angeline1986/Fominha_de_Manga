from http.server import BaseHTTPRequestHandler
import json
import re
import threading
from urllib.parse import urlsplit

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.router import dispatch_get, dispatch_post
from central_v2.backend.routes.static import is_static_asset
from central_v2.backend.operational_log import emit


class Handler(BaseHTTPRequestHandler):
    _JOB_POLL_PATH = re.compile(r"/api/jobs/[a-f0-9]{32}\Z")

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
        try:
            self.wfile.write(response.body)
        except (BrokenPipeError, ConnectionResetError):
            return

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
        self._request_job_id = _response_job_id(response)
        self._send_response(response)
        if response is not None and self.path == "/api/shutdown":
            # Shutdown must run outside the serving thread.
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        status = str(args[1]) if len(args) > 1 else ""
        request_path = getattr(self, "path", "")
        method = getattr(self, "command", "")
        path = urlsplit(request_path).path
        if (
            method == "GET"
            and self._JOB_POLL_PATH.fullmatch(path)
            and status.startswith(("2", "304"))
        ):
            return
        status_code = int(status) if status.isdigit() else 0
        if method == "GET" and (200 <= status_code < 300 or status_code == 304) and is_static_asset(path):
            return
        level = "ERROR" if status_code >= 500 else "WARNING" if status_code >= 400 else "INFO"
        fields = {"método": method or "?", "rota": path or "?", "status": status or "?"}
        if len(args) > 2 and str(args[2]).isdigit():
            fields["bytes"] = int(args[2])
        emit(level, "acesso HTTP", component="HTTP",
             job_id=getattr(self, "_request_job_id", None), **fields)


def _response_job_id(response):
    if response is None or response.status != 202:
        return None
    try:
        job = json.loads(response.body.decode("utf-8")).get("job")
        identifier = job.get("id") if isinstance(job, dict) else None
        return identifier if isinstance(identifier, str) else None
    except (AttributeError, UnicodeDecodeError, ValueError):
        return None

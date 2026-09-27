from http.server import BaseHTTPRequestHandler
import threading

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.routes.shutdown import shutdown_response


class Handler(BaseHTTPRequestHandler):
    def _send_response(self, response):
        if response is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def do_GET(self):
        self._send_response(dispatch_get(self.path))

    def do_POST(self):
        response = shutdown_response(self.path)
        self._send_response(response)
        if response is not None:
            # Shutdown must run outside the serving thread.
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        return

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from central_v2.backend.routes.router import dispatch_get


HOST = "127.0.0.1"
PORT = 8090


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = dispatch_get(self.path)

        if response is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Central V2: http://{HOST}:{PORT}")
    print(f"Health:     http://{HOST}:{PORT}/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

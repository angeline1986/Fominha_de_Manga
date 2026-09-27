from http.server import ThreadingHTTPServer
import threading
import webbrowser

from central_v2.backend.http_handler import Handler
from orquestracao.central_session import server_session

HOST = "127.0.0.1"
PORT = 8090


def main():
    with server_session():
        server = ThreadingHTTPServer((HOST, PORT), Handler)
        print(f"Central V2: http://{HOST}:{PORT}", flush=True)
        print(f"Health:     http://{HOST}:{PORT}/health", flush=True)

        browser_timer = threading.Timer(0.6, lambda: webbrowser.open(f"http://{HOST}:{PORT}"))
        try:
            browser_timer.start()
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            browser_timer.cancel()
            server.server_close()


if __name__ == "__main__":
    main()

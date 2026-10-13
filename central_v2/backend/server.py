from http.server import ThreadingHTTPServer
import threading
import webbrowser

from central_v2.backend.http_handler import Handler
from central_v2.backend.operational_log import emit
from orquestracao.central_session import server_session

HOST = "127.0.0.1"
PORT = 8090


def main():
    with server_session():
        server = ThreadingHTTPServer((HOST, PORT), Handler)
        emit("INFO", "servidor iniciado", component="SERVER",
             url=f"http://{HOST}:{PORT}", health=f"http://{HOST}:{PORT}/health")

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

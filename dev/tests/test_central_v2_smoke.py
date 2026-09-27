import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from central_v2.backend.routes.router import RouteResponse
from central_v2.backend.server import Handler, ThreadingHTTPServer


class CentralV2SmokeTests(unittest.TestCase):
    def test_catalog_over_real_http_handler(self):
        payload = {
            "comix": ["Obra Teste"],
            "mangago": [],
            "ridi": [],
        }
        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        with patch(
            "central_v2.backend.http_handler.dispatch_get",
            return_value=RouteResponse(status=200, body=body),
        ) as dispatch:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                Handler,
            )
            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )

            try:
                thread.start()

                host, port = server.server_address
                base = f"http://{host}:{port}"

                with urllib.request.urlopen(
                    f"{base}/api/catalog",
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                    result = json.loads(response.read().decode("utf-8"))

                self.assertEqual(result, payload)
                dispatch.assert_called_once_with("/api/catalog")

            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_health_over_real_http_handler(self):
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            Handler,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )

        try:
            thread.start()

            host, port = server.server_address
            base = f"http://{host}:{port}"

            with urllib.request.urlopen(
                f"{base}/health",
                timeout=5,
            ) as response:
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(
                payload,
                {
                    "status": "ok",
                    "app": "central-v2",
                },
            )

            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(
                    f"{base}/nao-existe",
                    timeout=5,
                )

            self.assertEqual(context.exception.code, 404)

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


    def test_state_query_over_real_http_handler(self):
        payload = {
            "provider": "comix",
            "manga": "Smoke Manga",
            "chapters": [],
            "summary": {"chapters": 0},
        }
        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        with patch(
            "central_v2.backend.http_handler.dispatch_get",
            return_value=RouteResponse(status=200, body=body),
        ) as dispatch:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                Handler,
            )
            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )

            try:
                thread.start()

                host, port = server.server_address
                base = f"http://{host}:{port}"

                with urllib.request.urlopen(
                    f"{base}/api/state?provider=comix&manga=Smoke%20Manga",
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                    result = json.loads(response.read().decode("utf-8"))

                self.assertEqual(result, payload)
                dispatch.assert_called_once_with(
                    "/api/state?provider=comix&manga=Smoke%20Manga"
                )

            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

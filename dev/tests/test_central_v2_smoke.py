import json
import threading
import unittest
import urllib.error
import urllib.request

from central_v2.backend.server import Handler, ThreadingHTTPServer


class CentralV2SmokeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

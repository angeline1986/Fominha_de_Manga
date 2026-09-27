import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from central_v2.backend.server import Handler, ThreadingHTTPServer


class ShutdownTests(unittest.TestCase):
    def test_only_shutdown_post_stops_server_after_acknowledgement(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for path, method in [("/missing", "POST"), ("/api/shutdown", "GET")]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + path, method=method), timeout=5)
                self.assertEqual(error.exception.code, 404)
                self.assertTrue(thread.is_alive())
            with urlopen(Request(base + "/api/shutdown", method="POST"), timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response), {"status": "shutting_down"})
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

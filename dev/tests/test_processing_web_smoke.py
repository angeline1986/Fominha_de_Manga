import json
import threading
import unittest
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from interface_web import processing_web


class ProcessingWebSmokeTests(unittest.TestCase):
    def test_catalog_and_state_over_real_http_handler(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp)

            manga = output / "comix" / "Smoke Manga"
            (manga / "IMG").mkdir(parents=True)

            original_output = processing_web.OUTPUT
            processing_web.OUTPUT = output

            server = processing_web.ThreadingHTTPServer(
                ("127.0.0.1", 0),
                processing_web.Handler,
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
                    catalog = json.loads(response.read().decode("utf-8"))

                self.assertIn("Smoke Manga", catalog["comix"])

                with urllib.request.urlopen(
                    f"{base}/api/state?provider=comix&manga=Smoke%20Manga",
                    timeout=5,
                ) as response:
                    self.assertEqual(response.status, 200)
                    state = json.loads(response.read().decode("utf-8"))

                self.assertEqual(state["provider"], "comix")
                self.assertEqual(state["manga"], "Smoke Manga")
                self.assertEqual(state["chapters"], [])
                self.assertEqual(state["summary"]["chapters"], 0)

            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                processing_web.OUTPUT = original_output


if __name__ == "__main__":
    unittest.main()

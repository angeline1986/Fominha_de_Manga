import unittest
from types import SimpleNamespace
from unittest.mock import patch

from central_v2.backend.http_handler import Handler, _response_job_id
from central_v2.backend.routes.response import RouteResponse


class CentralV2TerminalLogTests(unittest.TestCase):
    def _handler(self, method, path):
        return SimpleNamespace(command=method, path=path,
                               _JOB_POLL_PATH=Handler._JOB_POLL_PATH)

    def test_successful_polling_is_suppressed(self):
        with patch("builtins.print") as output:
            Handler.log_message(self._handler("GET", "/api/jobs/" + "a" * 32),
                                '"GET %s HTTP/1.1" %s -', "/api/jobs", 200)
        output.assert_not_called()

    def test_static_success_is_suppressed(self):
        with patch("central_v2.backend.http_handler.is_static_asset", return_value=True), \
             patch("builtins.print") as output:
            Handler.log_message(self._handler("GET", "/assets/app.css?cache=1"),
                                '"GET %s HTTP/1.1" %s %s', "/assets/app.css", 200, 100)
        output.assert_not_called()

    def test_static_error_is_visible(self):
        for status, level in ((404, "WARNING"), (500, "ERROR")):
            with self.subTest(status=status), \
                 patch("central_v2.backend.http_handler.is_static_asset", return_value=False), \
                 patch("builtins.print") as output:
                Handler.log_message(self._handler("GET", "/missing.svg"),
                                    '"GET %s HTTP/1.1" %s %s', "/missing.svg", status, 0)
            self.assertIn(f"{level} [HTTP] acesso HTTP", output.call_args.args[0])
            self.assertIn(f"status={status}", output.call_args.args[0])

    def test_api_post_is_visible(self):
        with patch("builtins.print") as output:
            Handler.log_message(self._handler("POST", "/api/sommelier/execute"),
                                '"POST %s HTTP/1.1" %s %s', "/api/sommelier/execute", 202, 30)
        self.assertIn("INFO [HTTP] acesso HTTP", output.call_args.args[0])
        self.assertIn("/api/sommelier/execute", output.call_args.args[0])

    def test_api_job_acceptance_log_can_share_response_job_id(self):
        handler = self._handler("POST", "/api/sommelier/execute")
        handler._request_job_id = "a1b2c3d4" + "0" * 24
        with patch("builtins.print") as output:
            Handler.log_message(handler, '"POST %s HTTP/1.1" %s %s',
                                "/api/sommelier/execute", 202, 20)
        self.assertIn("[HTTP][a1b2c3]", output.call_args.args[0])

    def test_accepted_job_id_is_read_from_existing_response_body(self):
        response = RouteResponse(202, b'{"job":{"id":"a1b2c3d4"}}')
        self.assertEqual(_response_job_id(response), "a1b2c3d4")

    def test_polling_error_is_visible(self):
        with patch("builtins.print") as output:
            Handler.log_message(self._handler("GET", "/api/jobs/" + "b" * 32),
                                '"GET %s HTTP/1.1" %s %s', "/api/jobs", 500, 0)
        self.assertIn("ERROR [HTTP] acesso HTTP", output.call_args.args[0])

    def test_not_modified_polling_is_suppressed(self):
        with patch("builtins.print") as output:
            Handler.log_message(self._handler("GET", "/api/jobs/" + "c" * 32),
                                '"GET %s HTTP/1.1" %s %s', "/api/jobs", 304, 0)
        output.assert_not_called()


if __name__ == "__main__":
    unittest.main()

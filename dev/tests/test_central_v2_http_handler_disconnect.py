import unittest
from unittest.mock import Mock

from central_v2.backend.http_handler import Handler
from central_v2.backend.routes.response import RouteResponse


class HttpHandlerDisconnectTests(unittest.TestCase):
    def setUp(self):
        self.handler = Handler.__new__(Handler)
        self.handler.path = "/api/example"
        self.handler.send_response = Mock()
        self.handler.send_header = Mock()
        self.handler.end_headers = Mock()
        self.handler.wfile = Mock()

    def test_normal_response_is_written_with_existing_headers(self):
        response = RouteResponse(202, b"payload", "application/octet-stream")

        Handler._send_response(self.handler, response)

        self.handler.send_response.assert_called_once_with(202)
        self.handler.send_header.assert_any_call("Content-Type", "application/octet-stream")
        self.handler.send_header.assert_any_call("Content-Length", "7")
        self.handler.send_header.assert_any_call("Cache-Control", "no-store")
        self.handler.wfile.write.assert_called_once_with(b"payload")

    def test_disconnected_client_during_body_write_is_ignored(self):
        for error in (BrokenPipeError("broken pipe"), ConnectionResetError("reset")):
            with self.subTest(error=type(error).__name__):
                self.handler.wfile.write.side_effect = error
                Handler._send_response(self.handler, RouteResponse(200, b"body"))

    def test_unexpected_body_write_error_still_propagates(self):
        self.handler.wfile.write.side_effect = RuntimeError("unexpected")

        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            Handler._send_response(self.handler, RouteResponse(200, b"body"))


if __name__ == "__main__":
    unittest.main()

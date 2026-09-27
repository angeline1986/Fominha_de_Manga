import unittest
from unittest.mock import patch

from central_v2.backend.http_handler import Handler


class CentralV2TerminalLogTests(unittest.TestCase):
    def test_http_log_is_printed_immediately_with_v2_prefix(self):
        with patch("builtins.print") as output:
            Handler.log_message(None, '"GET %s HTTP/1.1" %s -', "/api/jobs/abc", 200)

        output.assert_called_once_with(
            '[central-v2] "GET /api/jobs/abc HTTP/1.1" 200 -', flush=True,
        )


if __name__ == "__main__":
    unittest.main()

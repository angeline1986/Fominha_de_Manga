import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.server import Handler, ThreadingHTTPServer
from dev.tests.auto_merge_query_fixtures import QueryFixtures


class Level1HTTPTests(QueryFixtures, unittest.TestCase):
    def test_query_over_http_is_read_only_and_post_does_not_execute(self):
        self.stage(kind='partial', artifacts=[], pending_segments=[{'global_start': 0, 'global_end': 100}])
        before = self.snapshot()
        with patch('central_v2.backend.http_handler.dispatch_get', side_effect=lambda path: dispatch_get(path, self.output)):
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}/api/auto-merge/level1'
            try:
                with urlopen(base + '?provider=comix&manga=Obra%20Teste', timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.load(response)
                self.assertEqual(payload['chapters'][0]['level1']['kind'], 'partial')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base, method='POST'), timeout=5)
                self.assertEqual(error.exception.code, 404)
                self.assertEqual(self.snapshot(), before)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()

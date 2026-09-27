from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orquestracao.central_session import central_session, run_central


class CentralSessionTests(unittest.TestCase):
    def test_only_one_central_menu_session_can_hold_the_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "central.lock"
            with central_session(lock):
                with self.assertRaisesRegex(RuntimeError, "Outra Central"):
                    with central_session(lock):
                        pass
            with central_session(lock):
                pass

    def test_menu_holds_lease_until_server_subprocess_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "central.lock"
            with patch("orquestracao.central_session.LOCK_PATH", lock):
                def assert_locked(*args, **kwargs):
                    with self.assertRaises(RuntimeError):
                        with central_session(lock):
                            pass
                    self.assertEqual(kwargs["env"]["FOMINHA_CENTRAL_SESSION_HELD"], "1")

                with patch("subprocess.run", side_effect=assert_locked):
                    run_central(["python", "server.py"], Path.cwd())
                with central_session(lock):
                    pass


if __name__ == "__main__":
    unittest.main()

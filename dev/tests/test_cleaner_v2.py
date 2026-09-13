import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from processamento.limpeza_baloes.cleaner_v2 import launcher


class CleanerV2Tests(unittest.TestCase):
    def test_missing_environment_has_installation_guidance(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(launcher, 'MODULE_DIR', Path(tmp)):
            with self.assertRaisesRegex(FileNotFoundError, 'README.md'):
                launcher.build_command(Path(tmp), Path(tmp) / 'out', offline=False)

    def test_command_and_input_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / 'module'
            python = module / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            source = root / 'input with spaces'
            source.mkdir()
            with patch.object(launcher, 'MODULE_DIR', module):
                command = launcher.build_command(source, root / 'output', offline=True)
                self.assertIn(str(source.resolve()), command)
                self.assertIn('--offline', command)
                self.assertIn(str(module / 'outlined-text.ini'), command)
                self.assertEqual(command[0], str(python))
                for destination in (source, source / 'output', root):
                    with self.assertRaises(ValueError):
                        launcher.build_command(source, destination, offline=False)
                self.assertNotIn('--offline', launcher.build_command(source, root / 'output', offline=False))


if __name__ == '__main__':
    unittest.main()

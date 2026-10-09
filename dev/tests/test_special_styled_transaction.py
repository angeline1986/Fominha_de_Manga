"""Failure recovery tests for coordinated Artístico publication."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import special_styled_transaction as tx


class StyledTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "manga"
        self.manga.mkdir()

    def _entries(self, root, folder):
        entries = []
        for name in ("artistico", "final", "special"):
            target = root / name
            target.mkdir()
            (target / "manifest.json").write_text(f"old-{name}")
            staged = folder / f"stage-{name}"
            staged.mkdir()
            (staged / "manifest.json").write_text(f"new-{name}")
            entries.append({"target": str(target), "staged": str(staged)})
        return entries

    def test_failure_at_each_publish_replace_restores_all_targets(self):
        for fail_at in range(1, 9):
            with self.subTest(fail_at=fail_at):
                case = self.manga / str(fail_at)
                case.mkdir()
                identity, folder = tx.begin(case, "4")
                entries = self._entries(case, folder)
                original = tx.os.replace
                calls, failed = 0, False

                def fail_once(source, destination):
                    nonlocal calls, failed
                    calls += 1
                    if calls == fail_at and not failed:
                        failed = True
                        raise OSError("simulated publish interruption")
                    return original(source, destination)

                with patch.object(tx.os, "replace", side_effect=fail_once):
                    with self.assertRaises(OSError):
                        tx.publish(case, folder, entries, lambda: None)
                for name in ("artistico", "final", "special"):
                    self.assertEqual((case / name / "manifest.json").read_text(),
                                     f"old-{name}")
                self.assertFalse(folder.exists())

    def test_participating_reader_waits_until_all_targets_are_published(self):
        identity, folder = tx.begin(self.manga, "4")
        entries = self._entries(self.manga, folder)
        replaced, release, reader_done, writer_done = Event(), Event(), Event(), Event()
        original = tx.os.replace

        def pause_after_first_target(source, destination):
            result = original(source, destination)
            if Path(source).name == "stage-artistico":
                replaced.set()
                self.assertTrue(release.wait(2))
            return result

        with patch.object(tx.os, "replace", side_effect=pause_after_first_target):
            publisher = Thread(target=tx.publish,
                args=(self.manga, folder, entries, lambda: None))
            publisher.start()
            self.assertTrue(replaced.wait(2))

            def read_chapter():
                with tx.transaction_lock(self.manga):
                    states = [(self.manga / name / "manifest.json").read_text()
                              for name in ("artistico", "final", "special")]
                    self.assertEqual(states, ["new-artistico", "new-final", "new-special"])
                reader_done.set()

            reader = Thread(target=read_chapter)
            reader.start()
            def write_chapter():
                with tx.transaction_lock(self.manga):
                    state = (self.manga / "final/manifest.json").read_text()
                    self.assertEqual(state, "new-final")
                    (self.manga / "writer-observed.json").write_text(state)
                writer_done.set()

            writer = Thread(target=write_chapter)
            writer.start()
            time.sleep(.05)
            self.assertFalse(reader_done.is_set())
            self.assertFalse(writer_done.is_set())
            release.set()
            publisher.join(2)
            reader.join(2)
            writer.join(2)
        self.assertFalse(publisher.is_alive())
        self.assertTrue(reader_done.is_set())
        self.assertTrue(writer_done.is_set())
        self.assertEqual((self.manga / "writer-observed.json").read_text(), "new-final")

    def test_recovery_after_process_interruption_restores_previous_tree(self):
        identity, folder = tx.begin(self.manga, "4")
        entries = self._entries(self.manga, folder)
        item = {"target": "artistico", "staged": "stage-artistico",
                "backup": "backup-0", "had_previous": True}
        target, staged, backup = tx._paths(self.manga.resolve(), folder, item)
        target.rename(backup)
        staged.rename(target)
        journal = {"id": identity, "chapter": "4", "state": "publishing",
                   "entries": [item]}
        tx._write(folder / "journal.json", journal)

        with tx.transaction_lock(self.manga):
            self.assertEqual((self.manga / "artistico/manifest.json").read_text(),
                             "old-artistico")
        self.assertFalse(folder.exists())
        self.assertEqual((self.manga / "final/manifest.json").read_text(), "old-final")
        self.assertEqual((self.manga / "special/manifest.json").read_text(), "old-special")


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
from pathlib import Path
import tempfile


class QueryFixtures:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / 'output'
        self.manga = self.output / 'comix' / 'Obra Teste'
        self.chapter('1')

    def chapter(self, name):
        path = self.manga / 'IMG' / name
        path.mkdir(parents=True, exist_ok=True)
        # Not an image: the query must never decode pixels.
        (path / 'page-001.png').write_bytes(b'query fixture')
        return path

    def stage(self, chapter='1', kind='complete', **changes):
        directory = self.manga / 'FLUXO_SECUNDARIO' / '01_MERGE_PROCESSAMENTO' / 'AUTO_MERGE' / chapter
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            'schema_version': 1,
            'algorithm': 'auto_merge_level1_complete' if kind == 'complete' else 'auto_merge_level1_resolved_segments',
            'chapter': chapter, 'total_height': 100,
            'artifacts': [{'file': 'page-001.png', 'global_start': 0, 'global_end': 100}],
            'pending_segments': [],
        }
        payload.update(changes)
        manifest = directory / 'auto-merge-manifest.json'
        manifest.write_text(json.dumps(payload), encoding='utf-8')
        return directory, manifest

    def attempt(self, payload):
        path = self.manga / 'FLUXO_SECUNDARIO' / '01_MERGE_PROCESSAMENTO' / 'MERGE_STATUS' / '1' / 'merge-attempt.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def snapshot(self):
        return {
            str(path.relative_to(self.output)): (
                hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns,
            )
            for path in self.output.rglob('*') if path.is_file()
        }

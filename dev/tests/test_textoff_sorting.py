import json
import tempfile
import unittest
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.query import query_merged


class TextoffSortingTests(unittest.TestCase):
    def test_chapter_rows_use_natural_ascending_order(self):
        with tempfile.TemporaryDirectory() as root:
            manga = Path(root)
            for name in ("Ch. 10", "Ch. 2"):
                (manga / "IMG" / name).mkdir(parents=True)
                merge = manga / "FLUXO_SECUNDARIO/02_MERGE" / name
                merge.mkdir(parents=True)
                (merge / "page-001-005.png").write_bytes(b"merge")
                manifest = {"merged_images": 1, "source_total_height": 5,
                            "outputs": [{"file": "page-001-005.png", "global_start": 0,
                                         "global_end": 5}]}
                (merge / "merge-manifest.json").write_text(json.dumps(manifest))

            rows = query_merged(manga)["chapters"]

            self.assertEqual([row["chapter"] for row in rows], ["Ch. 2", "Ch. 10"])


if __name__ == "__main__":
    unittest.main()

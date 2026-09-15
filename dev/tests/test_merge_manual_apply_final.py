from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from processamento.merge_manual.finalizer import _build_candidate, _validate_sources
from processamento.merge_manual.proposal import _fp, _hash


class MergeManualApplyFinalTests(unittest.TestCase):
    def piece(self, a, b, stage="x"):
        return {
            "source": Path(f"/tmp/{stage}-{a}-{b}.png"),
            "source_file": f"{stage}-{a}-{b}.png",
            "global_start": a,
            "global_end": b,
            "source_stage": stage,
        }

    def test_candidate_exact_coverage(self):
        pieces = _build_candidate(
            automatic=[self.piece(0, 100, "auto"), self.piece(200, 300, "auto")],
            manual=[self.piece(100, 150, "manual"), self.piece(150, 200, "manual")],
            selected_start=100,
            selected_end=200,
            pending=[(100, 200)],
            total_height=300,
        )
        self.assertEqual([(x["global_start"], x["global_end"]) for x in pieces],
                         [(0,100),(100,150),(150,200),(200,300)])

    def test_gap_aborts(self):
        with self.assertRaisesRegex(ValueError, "GAP"):
            _build_candidate(
                automatic=[self.piece(0, 90, "auto"), self.piece(200, 300, "auto")],
                manual=[self.piece(100, 200, "manual")],
                selected_start=100,
                selected_end=200,
                pending=[(100, 200)],
                total_height=300,
            )

    def test_overlap_aborts(self):
        # O overlap precisa existir fora da faixa manual. Artefatos automáticos
        # que cruzam a faixa [selected_start, selected_end) são descartados por
        # contrato antes da composição candidata.
        with self.assertRaisesRegex(ValueError, "OVERLAP"):
            _build_candidate(
                automatic=[
                    self.piece(0, 100, "auto"),
                    self.piece(90, 100, "auto_dup"),
                    self.piece(200, 300, "auto"),
                ],
                manual=[self.piece(100, 200, "manual")],
                selected_start=100,
                selected_end=200,
                pending=[(100, 200)],
                total_height=300,
            )

    def test_other_pending_residual_aborts(self):
        with self.assertRaisesRegex(ValueError, "resíduos pendentes fora"):
            _build_candidate(
                automatic=[self.piece(0,100), self.piece(200,250)],
                manual=[self.piece(100,200,"manual")],
                selected_start=100,
                selected_end=200,
                pending=[(100,200),(250,300)],
                total_height=300,
            )

    def test_changed_source_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            chapter = Path(td)
            img = chapter/"page-001.png"
            Image.new("RGB",(10,10),"white").save(img)
            st=img.stat()
            source={
                "name":img.name,
                "size":st.st_size,
                "mtime_ns":st.st_mtime_ns,
                "sha256":_hash(img),
                "source_y_start":0,
                "source_y_end":10,
                "pending_height":10,
            }
            manifest={"source_files":[source],"source_fingerprint":_fp([source])}
            Image.new("RGB",(10,10),"black").save(img)
            with self.assertRaisesRegex(ValueError, "obsoleta"):
                _validate_sources(chapter, manifest)


if __name__=="__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from processamento.merge_manual.finalizer import apply_final_composition
from processamento.merge_manual.proposal import generate_proposal, list_saved_proposals
from processamento.merge_manual.selected_ranges import read_selected_ids
from processamento.merge_manual.service import build_read_state
from processamento.unificacao_imagens import image_stitcher
from central_v2.backend.routes.merge_manual_applied import applied_manual_ranges


class ProgressiveManualMergeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.manga = Path(self.temporary.name) / "comix" / "Synthetic"
        self.chapter = self.manga / "IMG" / "6"
        self.chapter.mkdir(parents=True)
        for number in range(1, 7):
            Image.new("RGB", (12, 20), "white").save(self.chapter / f"page-{number:03d}.png")
        automatic = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/AUTO_MERGE/6"
        automatic.mkdir(parents=True)
        Image.new("RGB", (12, 20), "white").save(automatic / "top.png")
        Image.new("RGB", (12, 20), "white").save(automatic / "bottom.png")
        (automatic / "auto-merge-manifest.json").write_text(json.dumps({"artifacts": [
            {"file": "top.png", "global_start": 0, "global_end": 20},
            {"file": "bottom.png", "global_start": 100, "global_end": 120},
        ]}), encoding="utf-8")
        self.review = {"needs_review": True, "merge_state": "pendente_review",
                       "merge_level5_detail": {"available": True, "valid": True,
                                               "review_pending_segments": [{"global_start": 20, "global_end": 100}]}}

    def tearDown(self):
        self.temporary.cleanup()

    def proposal(self, start, end, cut):
        return generate_proposal(self.manga, self.chapter, review_row=self.review,
                                 block_id="pending-1", start_file=start, end_file=end, cuts=[cut])

    def apply(self, proposal):
        return apply_final_composition(self.manga, self.chapter, review_row=self.review,
                                       proposal_id=proposal["proposal_id"])

    def test_selects_one_range_then_publishes_after_the_last_range(self):
        first = self.proposal("page-002.png", "page-003.png", 20)
        alternative = self.proposal("page-002.png", "page-003.png", 21)
        last = self.proposal("page-004.png", "page-005.png", 20)

        initial = self.apply(first)
        self.assertEqual(initial["status"], "FAIXA_SELECIONADA")
        self.assertEqual(initial["remaining_intervals"], [(60, 100)])
        self.assertEqual(read_selected_ids(self.manga, "6"), [first["proposal_id"]])
        self.assertFalse((self.manga / "FLUXO_SECUNDARIO/02_MERGE/6/merge-manifest.json").exists())
        state = build_read_state(self.manga, [self.chapter], review_state_loader=lambda _: self.review)
        self.assertTrue(state["chapters"][0]["manual_range_confirmed"])
        self.assertEqual(state["chapters"][0]["pending_pages"], 2)
        self.assertEqual(state["chapters"][0]["pending_blocks"][0]["first_page"], "page-004.png")
        statuses = {item["proposal_id"]: item["status"] for item in list_saved_proposals(self.manga)}
        self.assertEqual(statuses[first["proposal_id"]], "FAIXA_SELECIONADA")
        self.assertEqual(statuses[alternative["proposal_id"]], "ALTERNATIVA_SUBSTITUIDA")
        self.assertEqual(statuses[last["proposal_id"]], "PROPOSTA_GERADA")
        self.assertEqual(self.apply(first)["already_selected"], True)

        finished = self.apply(last)
        self.assertEqual(finished["status"], "EFETIVADO")
        official = self.manga / "FLUXO_SECUNDARIO/02_MERGE/6/merge-manifest.json"
        manifest = json.loads(official.read_text(encoding="utf-8"))
        self.assertEqual(manifest["composition"]["manual_proposal_ids"], [first["proposal_id"], last["proposal_id"]])
        self.assertTrue(image_stitcher.is_chapter_merged(self.chapter))
        self.assertEqual([(item["global_start"], item["global_end"]) for item in applied_manual_ranges(self.manga, "6")],
                         [(20, 60), (60, 100)])
        statuses = {item["proposal_id"]: item["status"] for item in list_saved_proposals(self.manga)}
        self.assertEqual(statuses[first["proposal_id"]], "EFETIVADO")
        self.assertEqual(statuses[last["proposal_id"]], "EFETIVADO")
        self.assertEqual(statuses[alternative["proposal_id"]], "ALTERNATIVA_SUBSTITUIDA")

    def test_failed_publication_restores_all_selected_proposals(self):
        first = self.proposal("page-002.png", "page-003.png", 20)
        last = self.proposal("page-004.png", "page-005.png", 20)
        self.apply(first)
        original_write = Path.write_text
        updates = 0

        def fail_last_status(path, content, *args, **kwargs):
            nonlocal updates
            if path.name == "merge-manual-manifest.json" and json.loads(content).get("status") == "EFETIVADO":
                updates += 1
                if updates == 2:
                    raise OSError("Falha simulada ao registrar a última proposta")
            return original_write(path, content, *args, **kwargs)

        with patch.object(Path, "write_text", fail_last_status):
            with self.assertRaisesRegex(OSError, "Falha simulada"):
                self.apply(last)
        self.assertFalse((self.manga / "FLUXO_SECUNDARIO/02_MERGE/6/merge-manifest.json").exists())
        self.assertEqual(read_selected_ids(self.manga, "6"), [first["proposal_id"]])
        statuses = {item["proposal_id"]: item["status"] for item in list_saved_proposals(self.manga)}
        self.assertEqual(statuses[first["proposal_id"]], "FAIXA_SELECIONADA")
        self.assertEqual(statuses[last["proposal_id"]], "PROPOSTA_GERADA")


if __name__ == "__main__":
    unittest.main()

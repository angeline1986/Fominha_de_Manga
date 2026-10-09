"""Artístico execution route submits work to the existing styled runner."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    rebuild_special_treatments,
)
from central_v2.backend.routes.router import dispatch_post


class StyledRouteTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        (self.manga / "IMG/1").mkdir(parents=True)
        check = manifest_path(self.manga, "1")
        check.parent.mkdir(parents=True)
        check.write_text(json.dumps({"schema": SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": [{
                "id": "styled-1", "page": "page.png", "tipo": "balao_estilizado",
                "box_normalized": {"left": .2, "top": .2, "width": .3, "height": .3},
                "box_pixels": {"x": 20, "y": 20, "width": 30, "height": 30}}]}))
        rebuild_special_treatments(self.manga, {"provider": "comix",
            "obra": "Example", "capitulo": "1"}, "1")

    def test_artistico_submits_to_its_own_executor(self):
        payload = {"provider": "comix", "manga": "Example",
                   "treatment": "estilizado", "chapters": ["1"]}
        with patch("central_v2.backend.routes.special_treatments.submit",
                   return_value={"id": "job"}) as submit, \
             patch("central_v2.backend.routes.special_treatments.execute_styled",
                   return_value=[]) as execute:
            response = dispatch_post("/api/textoff/special/treatments/execute",
                                     payload, self.root)
            self.assertEqual(response.status, 202)
            submit.call_args.args[0](lambda *_: None, "job")
            self.assertEqual(execute.call_args.args[2], ["1"])

    def test_reexecution_rejects_missing_occurrence_selection(self):
        payload = {"provider": "comix", "manga": "Example", "treatment": "estilizado",
                   "chapters": ["1"], "reexecute": True}
        response = dispatch_post("/api/textoff/special/treatments/execute", payload, self.root)
        self.assertEqual(response.status, 400)

    def test_reexecution_passes_exact_validated_occurrence(self):
        selection = {"chapter": "1", "page": "page.png", "id": "styled-1",
                     "expected_sha256": "f" * 64}
        payload = {"provider": "comix", "manga": "Example", "treatment": "estilizado",
                   "chapters": ["1"], "reexecute": True, "selections": [selection]}
        with patch("central_v2.backend.routes.special_treatments.validate_styled_reexecution",
                   return_value={"1": [{key: selection[key] for key in ("page", "id", "expected_sha256")}]}) as validate, \
             patch("central_v2.backend.routes.special_treatments.submit",
                   return_value={"id": "job"}) as submit, \
             patch("central_v2.backend.routes.special_treatments.execute_styled",
                   return_value=[]) as execute:
            response = dispatch_post("/api/textoff/special/treatments/execute", payload, self.root)
            self.assertEqual(response.status, 202)
            validate.assert_called_once()
            submit.call_args.args[0](lambda *_: None, "job")
            self.assertEqual(execute.call_args.kwargs["selections"]["1"][0]["id"], "styled-1")

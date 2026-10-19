"""Testes sintéticos: nenhuma imagem ou manifesto operacional."""
import unittest
from copy import deepcopy
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_candidate_merge import (
    consolidate_transparent, default_sommelier_solid,
)


def row(identifier, source, box, kind=""):
    return {"id": identifier, "page": "p.png", "origin": source,
            "origins": [source], "candidate": True,
            "source_references": [{"origin": source, "candidate_type": kind}],
            "type": kind, "box": dict(zip(("left", "top", "width", "height"), box))}


class CandidateMergeTests(unittest.TestCase):
    def test_one_contained_merges_and_preserves_mapear_type(self):
        base = row("map", "MAPEAR", (.2, .2, .3, .3), "residuo_gradiente")
        t = row("tr", "TRANSPARENT_RECOGNITION", (.19, .19, .32, .32), "balao_transparente")
        result = consolidate_transparent([deepcopy(base)], [t])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "map")
        self.assertEqual(result[0]["type"], "residuo_gradiente")
        self.assertIn("TRANSPARENT_RECOGNITION", result[0]["origins"])

    def test_ambiguous_overlap_remains_separate(self):
        a = row("a", "MAPEAR", (.1, .1, .2, .2))
        b = row("b", "SOMMELIER", (.25, .1, .2, .2))
        t = row("tr", "TRANSPARENT_RECOGNITION", (.2, .1, .2, .2))
        self.assertEqual(len(consolidate_transparent([a, b], [t])), 3)

    def test_partial_overlap_without_containment_is_separate(self):
        a = row("a", "MAPEAR", (.1, .1, .2, .2))
        t = row("t", "TRANSPARENT_RECOGNITION", (.2, .2, .2, .2))
        self.assertEqual(len(consolidate_transparent([a], [t])), 2)

    def test_fallback_only_sommelier_unknown(self):
        a = row("a", "SOMMELIER", (.1, .1, .2, .2))
        b = row("b", "MAPEAR", (.4, .4, .2, .2))
        result = default_sommelier_solid([a, b])
        self.assertEqual(result[0]["type"], "residuo_balao_solido_branco")
        self.assertEqual(result[1]["type"], "")

    def test_transparent_precedence_over_solid_fallback(self):
        a = row("a", "SOMMELIER", (.1, .1, .2, .2))
        t = row("t", "TRANSPARENT_RECOGNITION", (.09, .09, .22, .22), "balao_transparente")
        merged = consolidate_transparent([a], [t])
        self.assertEqual(len(merged), 1)
        self.assertEqual(default_sommelier_solid(merged)[0]["type"], "balao_transparente")


if __name__ == "__main__":
    unittest.main()

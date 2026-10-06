"""Conservative cross-source matching for Check suggestions."""
import unittest

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_geometry import (
    _merge_automatic_sources,
)


def normalized(x, y, width, height, image_width, image_height):
    return {"left": x / image_width, "top": y / image_height,
            "width": width / image_width, "height": height / image_height}


def source(origin, page, box, identity):
    if origin == "MAPEAR":
        reference = {"origin": origin, "stage": "TO_MERGED_NIVEL_III",
                     "report": "json/styled-balloon-report.json", "page": page,
                     "detection": identity, "candidate_type": "soft_gradient"}
        classification, kind = "soft_gradient", "residuo_gradiente"
    else:
        reference = {"origin": origin, "stage": "BUBBLE_SOMMELIER",
                     "report": "report.json", "page": page,
                     "identity": identity, "candidate": True, "label": 0}
        classification, kind = 0, ""
    return {"id": f"{origin.lower()}-{identity}", "page": page, "origin": origin,
            "origins": [origin], "source_references": [reference],
            "source_classification": classification, "candidate": True,
            "type": kind, "note": None, "box": box}


class AutoCleanerCheckDeduplicationTests(unittest.TestCase):
    def test_page_013_real_pair_merges_and_keeps_mapear_geometry_and_provenance(self):
        width, height = 940, 5886
        mapear = source("MAPEAR", "page-013-016.png",
                        normalized(227, 211, 541, 505, width, height), 1)
        sommelier = source("SOMMELIER", "page-013-016.png",
                           normalized(213.379638671875, 207.58657836914062,
                                      565.9917602539062, 522.5668029785156,
                                      width, height), "page-013-016-bubble-03")
        [merged] = _merge_automatic_sources([mapear], [sommelier])
        self.assertEqual(merged["box"], mapear["box"])
        self.assertEqual(merged["origins"], ["MAPEAR", "SOMMELIER"])
        self.assertEqual([ref["origin"] for ref in merged["source_references"]],
                         ["MAPEAR", "SOMMELIER"])
        self.assertEqual(merged["source_references"][0]["candidate_type"], "soft_gradient")
        self.assertEqual(merged["source_references"][1]["identity"],
                         "page-013-016-bubble-03")
        self.assertEqual(merged["source_references"][1]["label"], 0)
        self.assertTrue(merged["source_references"][1]["candidate"])

    def test_page_050_real_pairs_match_one_to_one_without_cross_pairing(self):
        width, height = 940, 6572
        mapear = [
            source("MAPEAR", "page-050-057.png",
                   normalized(453, 3763, 355, 283, width, height), 2),
            source("MAPEAR", "page-050-057.png",
                   normalized(113, 3378, 447, 355, width, height), 3),
        ]
        sommelier = [
            source("SOMMELIER", "page-050-057.png",
                   normalized(91.11268615722656, 3350.1692504882812,
                              485.13255310058594, 394.47991943359375,
                              width, height), "page-050-057-bubble-07"),
            source("SOMMELIER", "page-050-057.png",
                   normalized(440.87310791015625, 3739.677032470703,
                              381.26361083984375, 317.5027160644531,
                              width, height), "page-050-057-bubble-08"),
        ]
        merged = _merge_automatic_sources(mapear, sommelier)
        self.assertEqual(len(merged), 2)
        references = {row["source_references"][1]["identity"]:
                      row["source_references"][0]["detection"] for row in merged}
        self.assertEqual(references, {"page-050-057-bubble-07": 3,
                                      "page-050-057-bubble-08": 2})
        self.assertTrue(all(row["origins"] == ["MAPEAR", "SOMMELIER"] for row in merged))

    def test_exact_geometry_still_deduplicates(self):
        box = {"left": .2, "top": .2, "width": .3, "height": .2}
        merged = _merge_automatic_sources(
            [source("MAPEAR", "page.png", box, 1)],
            [source("SOMMELIER", "page.png", dict(box), "bubble-1")],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["origins"], ["MAPEAR", "SOMMELIER"])

    def test_nearby_overlapping_distinct_boxes_remain_separate(self):
        mapear = source("MAPEAR", "page.png",
                        {"left": .1, "top": .1, "width": .2, "height": .2}, 1)
        sommelier = source("SOMMELIER", "page.png",
                           {"left": .25, "top": .1, "width": .2, "height": .2}, "bubble-2")
        result = _merge_automatic_sources([mapear], [sommelier])
        self.assertEqual(len(result), 2)
        self.assertEqual({row["origins"][0] for row in result}, {"MAPEAR", "SOMMELIER"})

    def test_ambiguous_containment_is_left_unmerged(self):
        mapear = source("MAPEAR", "page.png",
                        {"left": .3, "top": .3, "width": .2, "height": .2}, 1)
        outer = source("SOMMELIER", "page.png",
                       {"left": .2, "top": .2, "width": .5, "height": .5}, "outer")
        inner = source("SOMMELIER", "page.png",
                       {"left": .25, "top": .25, "width": .3, "height": .3}, "inner")
        self.assertEqual(len(_merge_automatic_sources([mapear], [outer, inner])), 3)

    def test_containment_is_not_used_when_another_cross_source_box_overlaps(self):
        containing = source("MAPEAR", "page.png",
                            {"left": .2, "top": .2, "width": .3, "height": .3}, 1)
        neighbor = source("MAPEAR", "page.png",
                          {"left": .45, "top": .25, "width": .2, "height": .2}, 2)
        sommelier = source("SOMMELIER", "page.png",
                           {"left": .3, "top": .25, "width": .2, "height": .2}, "bubble")
        self.assertEqual(len(_merge_automatic_sources([containing, neighbor], [sommelier])), 3)


if __name__ == "__main__":
    unittest.main()

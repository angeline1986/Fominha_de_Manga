import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import special_levels


class MergedSpecialLevelTests(unittest.TestCase):
    def test_levels_four_and_five_bind_their_dedicated_treatments(self):
        self.assertEqual(special_levels.TREATMENTS["IV"], "transparente")
        self.assertEqual(special_levels.TREATMENTS["V"], "transparente_legacy")

    def test_eligibility_uses_level_one_integrity_without_reading_level_two(self):
        rows = {"chapters": [{"chapter": "Ch. 1", "merge_valid": True}]}
        with patch.object(special_levels, "query_merged_level1", return_value=rows), \
             patch.object(special_levels, "_stage_manifest", return_value={"clean_artifacts": []}), \
             patch.object(special_levels, "_manifest_matches_merge", return_value=True):
            result = special_levels.query_special_level("manga", "IV")
        self.assertTrue(result["chapters"][0]["level1_ready"])
        self.assertEqual(result["chapters"][0]["special_level"], "IV")


if __name__ == "__main__":
    unittest.main()

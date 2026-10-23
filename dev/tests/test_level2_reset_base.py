import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.level2_reset_base import (
    RESET_BASE_CONTRACT, reset_base_contract_current,
)


class Level2ResetBaseContractTests(unittest.TestCase):
    def test_direct_level2_marks_pre_reset_outputs_stale(self):
        reset = {"kind": "CHECK_RESET", "path": "reset_merge/page.png",
                 "sha256": "a" * 64, "reset_id": "reset-1", "source": "MERGE"}
        with patch("central_v2.backend.orchestration.textoff_merged.level2_reset_base.current_reset_base",
                   return_value=reset):
            self.assertFalse(reset_base_contract_current(
                "/manga", "1", {"page_results": []}, ["page.png"]))
            self.assertTrue(reset_base_contract_current(
                "/manga", "1", {"reset_base_contract": RESET_BASE_CONTRACT,
                                  "page_results": [{"source": "page.png",
                                                    "reset_base_source": reset}]},
                ["page.png"]))

    def test_legacy_consumers_remain_valid_when_no_reset_exists(self):
        with patch("central_v2.backend.orchestration.textoff_merged.level2_reset_base.current_reset_base",
                   return_value=None):
            self.assertTrue(reset_base_contract_current(
                "/manga", "1", {"page_results": []}, ["page.png"]))


if __name__ == "__main__":
    unittest.main()

"""Contract checks for the declarative TextOff artifact migration registry."""
import json
from pathlib import Path
import unittest


REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "central_v2/backend/orchestration/textoff_merged/artifact-migration-registry.json"
)


class TextoffArtifactMigrationRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.stages = {stage["stage_id"]: stage for stage in cls.registry["stages"]}

    def test_registry_schema_and_read_write_mode(self):
        self.assertEqual(self.registry["schema"], "artifact_migration_registry_v1")
        self.assertEqual(self.registry["migration_mode"], "registry_only")
        self.assertIs(self.registry["legacy_read_enabled"], True)
        self.assertIs(self.registry["new_read_enabled"], False)
        self.assertIs(self.registry["dual_write_enabled"], False)
        for stage in self.registry["stages"]:
            self.assertIs(stage["dual_write"], False)

    def test_persistent_stages_are_mapped_to_approved_targets(self):
        expected = {
            "auto_cleaner": ("TO_MERGED_NIVEL_I", "01_AUTO_CLEANER"),
            "mapear": ("TO_MERGED_NIVEL_III", "02_MAPEAR"),
            "mapear_input_consolidado": (
                "TO_MERGED_CONSOLIDADO", "02_MAPEAR/INPUT_CONSOLIDADO",
            ),
            "bubble_sommelier": ("BUBBLE_SOMMELIER", "03_BUBBLE_SOMMELIER"),
            "auto_cleaner_transparencia_basica": (
                "TO_MERGED_NIVEL_II", "05_AUTO_CLEANER_TRANSPARENCIA/BASICA",
            ),
        }
        for stage_id, (legacy_path, target_path) in expected.items():
            with self.subTest(stage=stage_id):
                stage = self.stages[stage_id]
                self.assertEqual(stage["legacy_path"], legacy_path)
                self.assertEqual(stage["target_path"], target_path)
                self.assertEqual(stage["classification"], "PERSISTENT_STAGE"
                                 if stage_id != "mapear_input_consolidado"
                                 else "CONSOLIDATED_OUTPUT_INTERMEDIATE")
                self.assertEqual(stage["read_authority"], "legacy")
                self.assertEqual(stage["migration_status"], "mapped")
                self.assertIs(stage["validated"], False)
                self.assertTrue(stage["writers"])
                self.assertTrue(stage["readers"])

    def test_consolidated_is_mapear_input_not_terminal_output(self):
        consolidated = self.stages["mapear_input_consolidado"]
        self.assertEqual(consolidated["relationships"]["owned_by_stage_id"], "mapear")
        self.assertEqual(consolidated["relationships"]["relation"], "intermediate_input")
        self.assertIs(consolidated["relationships"]["not_terminal_output"], True)
        self.assertIn("mapear_input_consolidado",
                      self.stages["mapear"]["relationships"]["input_stage_ids"])
        self.assertNotIn("07_CONSOLIDADO", json.dumps(self.registry))

    def test_check_is_a_new_stage_without_a_legacy_path(self):
        check = self.stages["auto_cleaner_check"]
        self.assertIsNone(check["legacy_path"])
        self.assertEqual(check["target_path"], "04_AUTO_CLEANER_CHECK")
        self.assertEqual(check["classification"], "NEW_STAGE")
        self.assertEqual(check["read_authority"], "none")
        self.assertEqual(check["migration_status"], "new_stage")

    def test_residue_catalog_remains_an_independent_auxiliary(self):
        residue = self.stages["residue_occurrences"]
        self.assertEqual(residue["legacy_path"], "RESIDUE_OCCURRENCES")
        self.assertEqual(residue["target_path"], "RESIDUE_OCCURRENCES")
        self.assertEqual(residue["classification"], "AUXILIARY_MANIFEST")
        self.assertEqual(residue["migration_status"], "retained")
        self.assertIs(residue["validated"], True)
        self.assertEqual(residue["relationships"]["ownership"], "independent_auxiliary")
        self.assertIn("auto_cleaner_check",
                      residue["relationships"]["future_consumer_stage_ids"])
        self.assertIs(residue["relationships"]["future_consumption_is_declarative_only"], True)

    def test_preview_modes_stay_in_staging_without_persistent_targets(self):
        preview_ids = {
            "transparencia_normal", "transparencia_legada", "pincel_degrade",
            "pincel_artistico", "pincel_suave",
        }
        expected_storage = "reports/experimentos/textoff_especiais_v2/{run_id}"
        for stage_id in preview_ids:
            with self.subTest(stage=stage_id):
                stage = self.stages[stage_id]
                self.assertEqual(stage["classification"], "TRANSIENT_PREVIEW")
                self.assertEqual(stage["storage_path"], expected_storage)
                self.assertIsNone(stage["target_path"])
                self.assertEqual(stage["migration_status"], "retained_in_staging")
                self.assertEqual(stage["read_authority"], "staging")

    def test_future_equivalence_contract_has_no_fabricated_results(self):
        contract = self.registry["validation_contract"]
        self.assertEqual(set(contract["comparison_status_values"]), {
            "MATCH", "STRUCTURAL_MATCH", "MISMATCH", "MISSING_LEGACY",
            "MISSING_TARGET", "NOT_APPLICABLE",
        })
        self.assertEqual(set(contract["artifact_record_fields"]), {
            "artifact", "size_legacy", "size_target", "sha256_legacy",
            "sha256_target", "comparison_status",
        })
        for stage in self.registry["stages"]:
            self.assertEqual(stage["validation"]["artifacts"], [])
            if stage["stage_id"] != "residue_occurrences":
                self.assertIsNone(stage["validation"]["comparison_status"])


if __name__ == "__main__":
    unittest.main()

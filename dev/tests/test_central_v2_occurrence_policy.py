"""M1 characterization of the central occurrence-type protection policy."""
import unittest

from central_v2.backend.orchestration.textoff_merged.occurrence_policy import (
    OCCURRENCE_POLICIES,
    policy_for,
    protected_types_for_transparency_basic,
)


class OccurrencePolicyTests(unittest.TestCase):
    def test_all_seven_persisted_type_ids_have_explicit_policy(self):
        self.assertEqual(set(OCCURRENCE_POLICIES), {
            "residuo_transparencia", "residuo_degrade", "residuo_gradiente",
            "balao_estilizado", "fragmento_balao", "texto_residual", "outro",
        })

    def test_protection_policy_for_transparency_basic(self):
        self.assertEqual(protected_types_for_transparency_basic(), {
            "residuo_degrade", "residuo_gradiente", "balao_estilizado",
            "fragmento_balao", "outro",
        })
        self.assertFalse(policy_for("residuo_transparencia").protect_from_transparency_basic)
        self.assertFalse(policy_for("texto_residual").protect_from_transparency_basic)

    def test_unknown_type_is_rejected(self):
        for value in ("unknown", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy_for(value)

    def test_registry_entries_are_immutable(self):
        policy = policy_for("balao_estilizado")
        with self.assertRaises(AttributeError):
            policy.protect_from_transparency_basic = False


if __name__ == "__main__":
    unittest.main()

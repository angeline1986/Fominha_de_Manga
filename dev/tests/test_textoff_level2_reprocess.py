"""Explicit Level II rerun policy from HTTP request to stage validator."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import level2_validation
from central_v2.backend.routes import textoff_merged


class Level2ReprocessValidationTests(unittest.TestCase):
    def validate(self, status, reprocess=False):
        row = {"chapter": "1", "level2_status": status,
               "selectable": status == "pending"}
        with patch.object(level2_validation, "validate_selection", return_value=["1"]), \
             patch.object(level2_validation, "query_merged_level2",
                          return_value={"chapters": [row]}):
            return level2_validation.validate_level2_selection(
                Path("/unused"), ["1"], reprocess=reprocess)

    def test_pending_normal_execution_still_works(self):
        self.assertEqual(self.validate("pending"), ["1"])

    def test_normal_execution_rejects_completed_states(self):
        for status in ("processed", "no_change"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.validate(status)

    def test_explicit_reprocess_accepts_processed_and_no_change(self):
        for status in ("processed", "no_change"):
            with self.subTest(status=status):
                self.assertEqual(self.validate(status, True), ["1"])

    def test_reprocess_does_not_accept_invalid_stage_prerequisites(self):
        for status in ("invalid_merge", "missing_level1", "no_candidates"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.validate(status, True)

    def test_merge_validation_and_boolean_intent_remain_mandatory(self):
        with patch.object(level2_validation, "validate_selection",
                          side_effect=ValueError("MERGE inválido")):
            with self.assertRaisesRegex(ValueError, "MERGE inválido"):
                level2_validation.validate_level2_selection(
                    Path("/unused"), ["1"], reprocess=True)
        for value in (1, "true", None, []):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "Reprocessamento"):
                level2_validation.validate_level2_selection(
                    Path("/unused"), ["1"], reprocess=value)


class Level2ReprocessRouteTests(unittest.TestCase):
    def request(self, value, include=True):
        payload = {"provider": "comix", "manga": "work", "chapters": ["1"]}
        if include:
            payload["reprocess"] = value
        with patch.object(textoff_merged, "build_catalog", return_value={"comix": ["work"]}), \
             patch.object(textoff_merged, "resolve_manga", return_value=Path("/unused")), \
             patch.object(textoff_merged, "legacy_server_active", return_value=False), \
             patch.object(textoff_merged, "validate_level2_selection",
                          return_value=["1"]) as validator, \
             patch.object(textoff_merged, "execute_merged_level2", return_value=[]) as runner, \
             patch.object(textoff_merged, "submit", return_value={"id": "job"}) as submit:
            response = textoff_merged.execute_textoff_merged_level2_response(
                payload, Path("/unused"))
            if response.status == 202:
                operation = submit.call_args.args[0]
                operation(lambda *_args: None, "job")
            return response, validator, runner

    def test_explicit_true_reaches_route_validator_and_executor(self):
        response, validator, runner = self.request(True)
        self.assertEqual(response.status, 202)
        self.assertTrue(validator.call_args.kwargs["reprocess"])
        self.assertTrue(runner.call_args.kwargs["reprocess"])

    def test_absent_and_false_keep_normal_policy(self):
        for include in (False, True):
            with self.subTest(include=include):
                response, validator, runner = self.request(False, include)
                self.assertEqual(response.status, 202)
                self.assertFalse(validator.call_args.kwargs["reprocess"])
                self.assertFalse(runner.call_args.kwargs["reprocess"])

    def test_ambiguous_values_are_rejected_before_job_creation(self):
        for value in (1, "true", None, {}):
            with self.subTest(value=value):
                response, validator, runner = self.request(value)
                self.assertEqual(response.status, 400)
                self.assertIn("Reprocessamento", json.loads(response.body)["error"])
                validator.assert_not_called()
                runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()

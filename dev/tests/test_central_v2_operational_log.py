import unittest
from unittest.mock import patch

from central_v2.backend.operational_log import bind_operation, emit


class OperationalLogTests(unittest.TestCase):
    def test_format_is_single_line_timestamped_and_correlated(self):
        with patch("builtins.print") as output:
            with bind_operation("SOMMELIER", "abcdef123456"):
                line = emit("info", "página\nconcluída", pagina="2/18", caminho="/Users/x/a.png")
        self.assertRegex(line, r"^\d{2}:\d{2}:\d{2}\.\d{3} INFO \[SOMMELIER\]\[abcdef\] ")
        self.assertNotIn("\n", line)
        self.assertIn("página concluída · pagina=2/18", line)
        self.assertIn("caminho=/Users/x/a.png", line)
        output.assert_called_once_with(line, flush=True)

    def test_context_is_isolated_between_operations(self):
        with patch("builtins.print") as output:
            with bind_operation("CLEANER-I", "12345678"):
                emit("INFO", "etapa")
            emit("INFO", "sem job")
        self.assertIn("[CLEANER-I][123456]", output.call_args_list[0].args[0])
        self.assertIn("[CENTRAL]", output.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()

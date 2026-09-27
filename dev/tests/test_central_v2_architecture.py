"""Guardrails for the V2 source tree; cohesion still requires code review."""
import ast
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2] / "central_v2"
FRONTEND = ROOT / "frontend"
SOURCE_EXTENSIONS = {".py", ".js", ".css", ".html"}
FEATURE_ROOTS = [
    ROOT.parent / "orquestracao" / "auto_merge",
    ROOT.parent / "processamento" / "unificacao_imagens" / "auto_merge",
]


class ArchitectureTests(unittest.TestCase):
    def test_source_files_have_at_most_200_lines(self):
        for path in (path for root in [ROOT, *FEATURE_ROOTS] for path in root.rglob("*")):
            if path.suffix in SOURCE_EXTENSIONS:
                with self.subTest(file=str(path.relative_to(ROOT.parent))):
                    self.assertLessEqual(len(path.read_text().splitlines()), 200)

    def test_frontend_network_calls_stay_in_api_modules(self):
        for path in FRONTEND.rglob("*.js"):
            if path.is_relative_to(FRONTEND / "_app" / "api"):
                continue
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertNotRegex(path.read_text(), r"\b(?:fetch|XMLHttpRequest)\s*\(")

    def test_backend_has_no_legacy_interface_dependency(self):
        roots = [ROOT / "backend", *FEATURE_ROOTS]
        for path in (path for root in roots for path in root.rglob("*.py")):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                with self.subTest(file=str(path.relative_to(ROOT.parent))):
                    self.assertFalse(any(name.split(".")[0] == "interface_web" for name in names))
                    if not path.is_relative_to(ROOT):
                        self.assertFalse(any(name.split(".")[0] == "central_v2" for name in names))

    def test_browser_module_and_stylesheet_paths_exist(self):
        for path in FRONTEND.rglob("*.js"):
            for target in re.findall(r'["\'](/[^"\']+\.js)["\']', path.read_text()):
                self.assertTrue((FRONTEND / target.lstrip("/")).is_file(), target)
        html = (FRONTEND / "index.html").read_text()
        for target in re.findall(r'href="(/[^"]+\.css)"', html):
            self.assertTrue((FRONTEND / target.lstrip("/")).is_file(), target)


if __name__ == "__main__":
    unittest.main()

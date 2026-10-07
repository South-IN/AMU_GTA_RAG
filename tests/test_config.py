from pathlib import Path
import unittest

from amu_admissions_rag.config import AppPaths, DEFAULT_PDF_NAME


class AppPathsTests(unittest.TestCase):
    def test_package_resolves_project_root(self) -> None:
        paths = AppPaths.from_package()

        # Avoid asserting the checkout directory name; it varies by machine and
        # filesystem case sensitivity.
        self.assertTrue((paths.project_root / "pyproject.toml").is_file())
        self.assertTrue((paths.project_root / "src" / "amu_admissions_rag").is_dir())
        self.assertEqual(paths.source_pdf.name, DEFAULT_PDF_NAME)

    def test_source_pdf_exists(self) -> None:
        paths = AppPaths.from_package()

        self.assertTrue(paths.source_pdf.is_file())
        self.assertGreater(paths.source_pdf.stat().st_size, 0)

    def test_output_directories_are_inside_project(self) -> None:
        paths = AppPaths.from_package()

        self.assertEqual(paths.processed_dir.parent, paths.project_root / "data")
        self.assertEqual(paths.review_dir.parent, paths.project_root / "data")
        self.assertIsInstance(paths.project_root, Path)


if __name__ == "__main__":
    unittest.main()


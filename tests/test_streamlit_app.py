import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_landing_page_renders_without_exceptions(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(app_path).run(timeout=15)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.chat_input), 1)
        self.assertEqual(
            app.chat_input[0].placeholder,
            "Ask about courses, eligibility, intake, selection or tests…",
        )
        button_labels = [button.label for button in app.button]
        self.assertIn("Clear conversation", button_labels)
        self.assertIn("How are candidates selected for M.B.A.?", button_labels)


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amu_admissions_rag.generation.groq import (
    DEFAULT_GROQ_MODEL,
    GroqAnswerGenerator,
    load_env_file,
)


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


class GroqGenerationTests(unittest.TestCase):
    def test_request_uses_gpt_oss_and_grounded_context(self) -> None:
        response = _FakeResponse(
            {"choices": [{"message": {"content": "Answer [SOURCE 1]"}}]}
        )
        with patch(
            "amu_admissions_rag.generation.groq.urlopen",
            return_value=response,
        ) as mocked_urlopen:
            answer = GroqAnswerGenerator("test-key").generate(
                "Can I do MCA?",
                "[SOURCE 1]\nMCA requires 16 credits.",
            )

        self.assertEqual(answer, "Answer [SOURCE 1]")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], DEFAULT_GROQ_MODEL)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(request.headers["User-agent"], "AMU-Admissions-RAG/0.1")
        self.assertEqual(request.headers["Accept"], "application/json")
        self.assertIn("MCA requires 16 credits", payload["messages"][1]["content"])
        self.assertIn("only from the supplied", payload["messages"][0]["content"])
        self.assertIn("potential matches", payload["messages"][0]["content"])

    def test_empty_context_abstains_without_api_call(self) -> None:
        with patch("amu_admissions_rag.generation.groq.urlopen") as mocked_urlopen:
            answer = GroqAnswerGenerator("test-key").generate("Unknown?", "  ")

        self.assertIn("insufficient", answer)
        mocked_urlopen.assert_not_called()

    def test_citation_repair_uses_constrained_prompt(self) -> None:
        response = _FakeResponse(
            {"choices": [{"message": {"content": "Answer [SOURCE 1]"}}]}
        )
        with patch(
            "amu_admissions_rag.generation.groq.urlopen",
            return_value=response,
        ) as mocked_urlopen:
            answer = GroqAnswerGenerator("test-key").repair_citations(
                "Question?",
                "[SOURCE 1]\nEvidence",
                "Answer without a citation",
            )

        self.assertEqual(answer, "Answer [SOURCE 1]")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("Repair citations", payload["messages"][0]["content"])
        self.assertIn("Answer without a citation", payload["messages"][1]["content"])

    def test_eligibility_repair_prohibits_inferred_qualification(self) -> None:
        response = _FakeResponse(
            {"choices": [{"message": {"content": "Potential match [SOURCE 1]"}}]}
        )
        with patch(
            "amu_admissions_rag.generation.groq.urlopen",
            return_value=response,
        ) as mocked_urlopen:
            answer = GroqAnswerGenerator("test-key").repair_eligibility_claims(
                "I have a B.Sc. Which courses fit?",
                "[SOURCE 1]\nRequires 55 percent and Mathematics credits.",
                "You qualify [SOURCE 1].",
            )

        self.assertEqual(answer, "Potential match [SOURCE 1]")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("never infer marks", payload["messages"][0]["content"])
        self.assertIn("You qualify", payload["messages"][1]["content"])

    def test_env_file_does_not_override_existing_process_value(self) -> None:
        original = os.environ.get("GROQ_MODEL")
        os.environ["GROQ_MODEL"] = "existing-model"
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / ".env"
                path.write_text("GROQ_MODEL=file-model\n", encoding="utf-8")
                load_env_file(path)
            self.assertEqual(os.environ["GROQ_MODEL"], "existing-model")
        finally:
            if original is None:
                os.environ.pop("GROQ_MODEL", None)
            else:
                os.environ["GROQ_MODEL"] = original


if __name__ == "__main__":
    unittest.main()

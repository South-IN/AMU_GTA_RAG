from pathlib import Path
import unittest


class DatabaseSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.schema = (root / "sql" / "001_retrieval_schema.sql").read_text(
            encoding="utf-8"
        )

    def test_schema_enables_full_text_and_vector_search(self) -> None:
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", self.schema)
        self.assertIn("search_vector TSVECTOR GENERATED ALWAYS AS", self.schema)
        self.assertIn("embedding vector", self.schema)
        self.assertIn("CREATE OR REPLACE FUNCTION hybrid_search_chunks", self.schema)

    def test_schema_enforces_approved_only_retrieval_chunks(self) -> None:
        self.assertIn(
            "review_status review_status NOT NULL CHECK (review_status = 'approved')",
            self.schema,
        )

    def test_schema_retains_parent_course_relationship(self) -> None:
        self.assertIn(
            "parent_course_id TEXT REFERENCES course_records(record_id)",
            self.schema,
        )
        self.assertIn("retrieval_chunks_parent_course_idx", self.schema)

    def test_schema_uses_rrf_for_hybrid_ranking(self) -> None:
        self.assertIn("FULL OUTER JOIN vector_candidates", self.schema)
        self.assertIn("1.0 / (rrf_k + text_candidates.rank_position)", self.schema)
        self.assertIn("1.0 / (rrf_k + vector_candidates.rank_position)", self.schema)


if __name__ == "__main__":
    unittest.main()

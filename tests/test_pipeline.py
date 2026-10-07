from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from amu_admissions_rag.config import AppPaths
from amu_admissions_rag.corpus import load_approved_corpora
from amu_admissions_rag.models import (
    CourseCorpus,
    DocumentRecord,
    ExtractedDocument,
    PolicyCorpus,
    ReviewBatch,
    ReviewDecision,
    ReviewStatus,
)
from amu_admissions_rag.pipeline import (
    ingestion_fingerprint,
    load_review_batches,
    run_pipeline,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _batch(reviewed_at: datetime, record_id: str) -> str:
    return ReviewBatch(
        reviewer="reviewer",
        reviewed_at=reviewed_at,
        decisions=[ReviewDecision(record_id=record_id, status=ReviewStatus.APPROVED)],
    ).model_dump_json()


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.paths = AppPaths(project_root=PROJECT_ROOT)

    def test_review_batches_are_ordered_by_review_time(self) -> None:
        (self.directory / "a.json").write_text(
            _batch(datetime(2026, 10, 9, tzinfo=timezone.utc), "later")
        )
        (self.directory / "b.json").write_text(
            _batch(datetime(2026, 10, 7, tzinfo=timezone.utc), "earlier")
        )

        batches = load_review_batches(self.directory)

        self.assertEqual([path.name for path, _ in batches], ["b.json", "a.json"])

    def test_fingerprint_changes_with_review_batches_and_pdf(self) -> None:
        baseline = ingestion_fingerprint("a" * 64, self.paths, self.directory)
        self.assertEqual(baseline, ingestion_fingerprint("a" * 64, self.paths, self.directory))
        self.assertNotEqual(baseline, ingestion_fingerprint("b" * 64, self.paths, self.directory))

        (self.directory / "batch.json").write_text(
            _batch(datetime(2026, 10, 7, tzinfo=timezone.utc), "record")
        )
        self.assertNotEqual(
            baseline, ingestion_fingerprint("a" * 64, self.paths, self.directory)
        )

    def test_corpus_loader_uses_json_without_database_url(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AMU_RAG_DATABASE_URL", None)
            with self.assertRaises(FileNotFoundError):
                load_approved_corpora(AppPaths(project_root=self.directory))

    def test_corpus_loader_prefers_database_url(self) -> None:
        with (
            mock.patch.dict(os.environ, {"AMU_RAG_DATABASE_URL": "postgresql://db"}),
            mock.patch("amu_admissions_rag.storage.PostgresIndexStore") as store,
        ):
            store.return_value.load_approved_corpora.return_value = ("index", "courses")
            self.assertEqual(
                load_approved_corpora(AppPaths(project_root=self.directory)),
                ("index", "courses"),
            )
        store.assert_called_once_with("postgresql://db")


class EmptyCorpusGuardTests(unittest.TestCase):
    """A fresh guide with no approvals loads; emptying a populated index does not."""

    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        (directory / "reviews").mkdir()
        self.paths = AppPaths(project_root=directory)
        document = DocumentRecord(
            document_id="guide",
            filename="guide.pdf",
            academic_year="2026-27",
            sha256="a" * 64,
            total_pages=1,
        )
        extractor = mock.Mock()
        extractor.document_record.return_value = document
        extractor.extract_pages.return_value = ExtractedDocument(document=document, pages=[])
        self.store = mock.Mock()
        self.store.apply_migrations.return_value = []
        self.store.latest_ingestion_fingerprint.return_value = None
        self.store.replace_approved_corpus.return_value = 0
        patches = [
            mock.patch("amu_admissions_rag.pipeline.PdfExtractor", return_value=extractor),
            mock.patch("amu_admissions_rag.pipeline.PostgresIndexStore", return_value=self.store),
            mock.patch("amu_admissions_rag.pipeline.ingestion_fingerprint", return_value="f" * 64),
            mock.patch(
                "amu_admissions_rag.pipeline.CourseParser.parse",
                return_value=CourseCorpus(document=document, courses=[]),
            ),
            mock.patch(
                "amu_admissions_rag.pipeline.PolicyParser.parse",
                return_value=PolicyCorpus(document=document, sections=[], appendix_rows=[]),
            ),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _run(self, **kwargs: bool) -> None:
        run_pipeline(
            paths=self.paths,
            database_url="postgresql://db",
            reviews_dir=self.paths.project_root / "reviews",
            log=lambda message: None,
            **kwargs,
        )

    def test_fresh_database_accepts_an_empty_corpus(self) -> None:
        self.store.approved_chunk_count.return_value = 0

        self._run()

        self.store.replace_approved_corpus.assert_called_once()

    def test_populated_database_is_not_emptied_by_accident(self) -> None:
        self.store.approved_chunk_count.return_value = 15

        with self.assertRaisesRegex(RuntimeError, "Refusing to empty"):
            self._run()
        self.store.replace_approved_corpus.assert_not_called()

        self._run(allow_empty=True)
        self.store.replace_approved_corpus.assert_called_once()


if __name__ == "__main__":
    unittest.main()
